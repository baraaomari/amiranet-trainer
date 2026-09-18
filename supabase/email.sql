-- تذكيرات الإيميل — شغّله مرة واحدة: Supabase ← SQL Editor ← New query ← Run
-- آمن للتكرار. الخطوات كاملة في EMAIL.md.
--
-- مين بيوصله إيميل (بتوقيت القدس):
--   exam_eve  : امتحانه بكرا — رسالة بالتوفيق، مرة وحدة لكل تاريخ امتحان.
--   comeback  : ما استعمل الموقع من ٣ أيام أو أكثر، وامتحانه مش بكرا ولا فات.
--               تذكير كل ٤ أيام بالكثير، وبحد أقصى ٣ تذكيرات لحد ما يرجع.
-- فقط الي وافق (email_prefs.reminders = true).

-- ═══ سر التذكيرات ═══
-- السكربت يستعمل المفتاح العام (anon) + هاد السر، مش service_role. لو تسرّب السر،
-- كل الي بيفتحه هو قائمة التذكيرات، مش قاعدة البيانات كلها.
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table if not exists private.settings (
  key   text primary key,
  value text not null
);
insert into private.settings (key, value)
values ('reminder_secret', replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''))
on conflict (key) do nothing;

create or replace function private.check_secret(p_secret text)
returns void language plpgsql as $$
begin
  if p_secret is null or p_secret is distinct from
     (select value from private.settings where key = 'reminder_secret') then
    raise exception 'forbidden' using errcode = '42501';
  end if;
end $$;

-- تاريخ من نص محفوظ بالأبب؛ أي قيمة غريبة بترجع null بدل ما توقف الاستعلام
create or replace function private.safe_date(t text)
returns date language plpgsql immutable as $$
begin
  return t::date;
exception when others then
  return null;
end $$;

-- ═══ موافقة كل طالب ═══
create table if not exists public.email_prefs (
  user_id    uuid        primary key references auth.users on delete cascade,
  reminders  boolean     not null default false,
  updated_at timestamptz not null default now()
);
alter table public.email_prefs enable row level security;
drop policy if exists email_prefs_own on public.email_prefs;
create policy email_prefs_own on public.email_prefs
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ═══ سجل الرسائل ═══
-- RLS مفعّل بدون أي policy: ما حدا بيوصله من الموقع، بس الدوال تحت.
create table if not exists public.email_log (
  id        bigserial   primary key,
  user_id   uuid        not null references auth.users on delete cascade,
  kind      text        not null check (kind in ('comeback', 'exam_eve')),
  exam_date date,
  sent_at   timestamptz not null default now()
);
alter table public.email_log enable row level security;
create index if not exists email_log_user_sent on public.email_log (user_id, sent_at desc);

-- ═══ مين لازم يوصله إيميل اليوم ═══
create or replace function public.reminder_candidates(p_secret text)
returns table (user_id uuid, email text, name text, lang text, kind text, exam_date date, days_left int)
language plpgsql security definer set search_path = public, private, auth
as $$
#variable_conflict use_column
declare
  today date := (now() at time zone 'Asia/Jerusalem')::date;
begin
  perform private.check_secret(p_secret);
  return query
  with base as (
    select
      u.id                                                         as uid,
      u.email::text                                                as mail,
      coalesce(nullif(m.data->>'name', ''), nullif(u.raw_user_meta_data->>'name', '')) as nm,
      case when m.data->>'lang' = 'en' then 'en' else 'ar' end    as lg,
      private.safe_date(s.data->>'examDate')                       as exam,
      -- أي استعمال: حفظ تقدّم (كلمات، تدريب، جدول) أو امتحان — مش بس الكلمات
      (greatest(
         u.created_at,
         (select max(a.updated_at) from public.app_state a where a.user_id = u.id),
         (select max(t.created_at) from public.attempts  t where t.user_id = u.id)
       ) at time zone 'Asia/Jerusalem')::date                      as last_active
    from auth.users u
    join public.email_prefs p on p.user_id = u.id and p.reminders
    left join public.app_state m on m.user_id = u.id and m.key = 'meta'
    left join public.app_state s on s.user_id = u.id and s.key = 'schedule'
    where u.email is not null
  )
  select b.uid, b.mail, b.nm, b.lg, 'exam_eve'::text, b.exam, 1
  from base b
  where b.exam = today + 1
    and not exists (select 1 from public.email_log l
                    where l.user_id = b.uid and l.kind = 'exam_eve' and l.exam_date = b.exam)
  union all
  select b.uid, b.mail, b.nm, b.lg, 'comeback'::text, b.exam, (b.exam - today)
  from base b
  where (b.exam is null or b.exam >= today + 2)
    and b.last_active <= today - 3
    and not exists (select 1 from public.email_log l
                    where l.user_id = b.uid and l.sent_at > now() - interval '4 days')
    and (select count(*) from public.email_log l
         where l.user_id = b.uid and l.kind = 'comeback'
           and (l.sent_at at time zone 'Asia/Jerusalem')::date >= b.last_active) < 3;
end $$;

create or replace function public.log_reminder(p_secret text, p_user uuid, p_kind text, p_exam date)
returns void language plpgsql security definer set search_path = public, private
as $$
begin
  perform private.check_secret(p_secret);
  insert into public.email_log (user_id, kind, exam_date) values (p_user, p_kind, p_exam);
end $$;

create or replace function public.unsubscribe_reminders(p_secret text, p_user uuid)
returns void language plpgsql security definer set search_path = public, private
as $$
begin
  perform private.check_secret(p_secret);
  insert into public.email_prefs (user_id, reminders) values (p_user, false)
  on conflict (user_id) do update set reminders = false, updated_at = now();
end $$;

-- السكربت بيتصل بالمفتاح العام؛ الدوال نفسها بترفض أي طلب بدون السر
revoke all on function public.reminder_candidates(text)                  from public;
revoke all on function public.log_reminder(text, uuid, text, date)        from public;
revoke all on function public.unsubscribe_reminders(text, uuid)           from public;
grant execute on function public.reminder_candidates(text)                to anon;
grant execute on function public.log_reminder(text, uuid, text, date)     to anon;
grant execute on function public.unsubscribe_reminders(text, uuid)        to anon;
revoke all on function private.check_secret(text) from public;
revoke all on function private.safe_date(text)    from public;


-- ═══ للمتابعة (للقراءة فقط) ═══
-- select value from private.settings where key = 'reminder_secret';      -- السر للسكربت
-- select count(*) filter (where reminders) as "وافقوا", count(*) as "جاوبوا" from public.email_prefs;
-- select sent_at::date as "اليوم", kind, count(*) from public.email_log group by 1, 2 order by 1 desc;
