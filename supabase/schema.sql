-- مخطط قاعدة البيانات لمدرّب أميرنت.
-- الصقه كاملاً في: Supabase → SQL Editor → New query → Run.
-- آمن للتشغيل أكثر من مرة.

-- ── حالة المستخدم: صف لكل مفتاح (meta / schedule / chat / srs:1 …) ──
create table if not exists public.app_state (
  user_id    uuid        not null references auth.users on delete cascade,
  key        text        not null,
  data       jsonb       not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (user_id, key)
);

-- ── محاولات الامتحانات ──
create table if not exists public.attempts (
  id         text        primary key,
  user_id    uuid        not null references auth.users on delete cascade,
  data       jsonb       not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists attempts_user_created
  on public.attempts (user_id, created_at desc);

-- ── أمان مستوى الصف: كل مستخدم يرى بياناته وحده، لا أحد غيره ──
alter table public.app_state enable row level security;
alter table public.attempts  enable row level security;

drop policy if exists app_state_own on public.app_state;
create policy app_state_own on public.app_state
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists attempts_own on public.attempts;
create policy attempts_own on public.attempts
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ── تحديث الطابع الزمني تلقائياً ──
create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists app_state_touch on public.app_state;
create trigger app_state_touch
  before update on public.app_state
  for each row execute function public.touch_updated_at();

-- ═══════════════════════════════════════════════════════════════
-- حدّ يومي لأسئلة المدرّس
-- الموقع مفتوح للتسجيل، وكل سؤال يُحاسَب على مفتاح صاحب الموقع.
-- بدون هذا الحدّ يستطيع أي مسجَّل استنزاف الرصيد.
-- ═══════════════════════════════════════════════════════════════

create table if not exists public.tutor_usage (
  user_id uuid not null references auth.users on delete cascade,
  day     date not null default current_date,
  count   int  not null default 0,
  primary key (user_id, day)
);

-- بلا سياسات: لا يلمسه إلا الخادم (service_role يتجاوز RLS)،
-- فلا يستطيع أحد قراءة عدّاده ولا تعديله من المتصفح.
alter table public.tutor_usage enable row level security;

-- زيادة ذرّية للعدّاد: تُرجع العدد الجديد، أو -1 إذا تجاوز الحدّ.
create or replace function public.bump_tutor_usage(p_user uuid, p_limit int)
returns int
language plpgsql
security definer
set search_path = public
as $$
declare n int;
begin
  insert into public.tutor_usage (user_id, day, count)
  values (p_user, current_date, 1)
  on conflict (user_id, day)
    do update set count = tutor_usage.count + 1
  returning count into n;

  if n > p_limit then
    return -1;
  end if;
  return n;
end $$;

revoke all on function public.bump_tutor_usage(uuid, int) from public, anon, authenticated;
