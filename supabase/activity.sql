-- قياس الرجوع — شغّله مرة واحدة: Supabase ← SQL Editor ← New query ← Run
-- آمن للتكرار. الموقع بيسجّل صف لكل يوم بيفوت فيه الطالب، و studied لما يدرس فعلاً
-- (كلمات، جولة تدريب، أو امتحان). ما بيحتاج إشي تاني منك.

create table if not exists public.activity_days (
  user_id uuid    not null references auth.users on delete cascade,
  day     date    not null,
  studied boolean not null default false,
  primary key (user_id, day)
);
alter table public.activity_days enable row level security;
drop policy if exists activity_own on public.activity_days;
create policy activity_own on public.activity_days
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);


-- ═══ للقراءة (بعد كم يوم من التشغيل) ═══
-- الرجوع حسب أول يوم فات فيه الطالب بعد هالتحديث:
-- with first as (select user_id, min(day) as d0 from public.activity_days group by user_id)
-- select f.d0 as "أول يوم", count(*) as "طلاب",
--   count(*) filter (where exists (select 1 from public.activity_days a where a.user_id = f.user_id and a.day = f.d0 + 1))            as "رجعوا تاني يوم",
--   count(*) filter (where exists (select 1 from public.activity_days a where a.user_id = f.user_id and a.day between f.d0 + 1 and f.d0 + 7)) as "رجعوا خلال أسبوع",
--   count(*) filter (where exists (select 1 from public.activity_days a where a.user_id = f.user_id and a.studied))                  as "درسوا فعلاً"
-- from first f group by 1 order by 1 desc;
--
-- كم واحد فات ودرس كل يوم:
-- select day as "اليوم", count(*) as "فاتوا", count(*) filter (where studied) as "درسوا"
-- from public.activity_days group by 1 order by 1 desc;
