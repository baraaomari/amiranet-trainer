-- ═══════════════════════════════════════════════════════════════════════
-- لوحة إحصائيات مدرّب أميرنت — للقراءة فقط، ما بتغيّر أي بيانات.
-- Supabase ← SQL Editor ← New query ← الصق **جزء واحد** ← Run
-- (Supabase بيعرض نتيجة آخر استعلام بس، فكل جزء لحاله.)
-- ═══════════════════════════════════════════════════════════════════════


-- ═══ ١. اللوحة الرئيسية: كل الأرقام بجدول واحد ═══
with
tz    as (select (now() at time zone 'Asia/Jerusalem')::date as today),
u     as (select id, (created_at at time zone 'Asia/Jerusalem')::date as joined from auth.users),
meta  as (
  select user_id,
    coalesce((data->>'totalReviews')::int, 0)                                   as reviews,
    coalesce((data->>'streak')::int, 0)                                         as streak,
    case when data->>'lastStudy' ~ '^\d{4}-\d{2}-\d{2}$' then (data->>'lastStudy')::date end as last_study,
    case when jsonb_typeof(data->'drills') = 'object'
         then (select count(*) from jsonb_object_keys(data->'drills')) else 0 end  as drills,
    case when jsonb_typeof(data->'unlocked') = 'array'
         then jsonb_array_length(data->'unlocked') else 1 end                   as levels_open,
    coalesce((data->>'onboarded')::boolean, false)                              as onboarded,
    data->>'dailyGoal'                                                          as goal,
    data->>'level'                                                              as lvl
  from public.app_state where key = 'meta'
),
sched as (
  select user_id,
    case when data->>'examDate' ~ '^\d{4}-\d{2}-\d{2}$' then (data->>'examDate')::date end as exam_date
  from public.app_state where key = 'schedule'
),
act   as (select user_id, (max(updated_at) at time zone 'Asia/Jerusalem')::date as last_active
          from public.app_state group by user_id),
att   as (select user_id, (data->>'score')::numeric as score from public.attempts where data ? 'score'),
studied as (select user_id from meta where reviews > 0 or drills > 0 union select user_id from att),
total as (select count(*)::numeric as n from u)
select * from (
            select 1  as "#", '👥 المسجّلين' as "المقياس", count(*)::text as "القيمة" from u
  union all select 2,  '   سجّلوا اليوم',            count(*)::text from u, tz where u.joined = tz.today
  union all select 3,  '   سجّلوا آخر ٧ أيام',       count(*)::text from u, tz where u.joined > tz.today - 7
  union all select 4,  '   سجّلوا آخر ٣٠ يوم',       count(*)::text from u, tz where u.joined > tz.today - 30
  union all select 5,  '🟢 نشطين اليوم',              count(*)::text from act, tz where act.last_active = tz.today
  union all select 6,  '   نشطين آخر ٧ أيام',        count(*)::text from act, tz where act.last_active > tz.today - 7
  union all select 7,  '📖 درسوا فعلاً (كلمات/تدريب/امتحان)',
                       count(*) || '  (' || round(100 * count(*) / nullif((select n from total), 0)) || '٪ من المسجّلين)' from studied
  union all select 8,  '   خلصوا أول دخول',          count(*)::text from meta where onboarded
  union all select 9,  '   حطّوا تاريخ امتحان',       count(*)::text from sched where exam_date is not null
  union all select 10, '   امتحانهم خلال ١٤ يوم',     count(*)::text from sched, tz
                       where exam_date between tz.today and tz.today + 14
  union all select 11, '   الوقت اليومي المختار',
                       format('5د: %s · 10د: %s · 20د: %s', count(*) filter (where goal = '5'),
                              count(*) filter (where goal = '10'), count(*) filter (where goal = '20')) from meta
  union all select 12, '   المستوى المختار',
                       format('مبتدئ: %s · متوسط: %s · قوي: %s', count(*) filter (where lvl = 'easy'),
                              count(*) filter (where lvl = 'medium'), count(*) filter (where lvl = 'hard')) from meta
  union all select 13, '🔤 مراجعات الكلمات (مجموع)', coalesce(sum(reviews), 0)::text from meta
  union all select 14, '   متوسط المراجعات لكل طالب درس', coalesce(round(avg(reviews) filter (where reviews > 0)), 0)::text from meta
  union all select 15, '   فتحوا المستوى ٢ أو أكثر',  count(*)::text from meta where levels_open >= 2
  union all select 16, '🎯 جولات تدريب مختلفة خلّصوها (مجموع)', coalesce(sum(drills), 0)::text from meta
  union all select 17, '📝 امتحانات منجزة',          count(*)::text from att
  union all select 18, '   طلاب عملوا امتحان',       count(distinct user_id)::text from att
  union all select 19, '   متوسط العلامة',           coalesce(round(avg(score)), 0)::text from att
  union all select 20, '   أعلى علامة',              coalesce(max(score), 0)::text from att
  union all select 21, '   امتحانات فوق ١٣٤ (פטור)',  count(*)::text from att where score >= 134
  union all select 22, '🔥 أطول سلسلة أيام',          coalesce(max(streak), 0)::text from meta
  union all select 23, '   سلسلتهم شغّالة ٣ أيام+',  count(*)::text from meta, tz
                       where streak >= 3 and last_study >= tz.today - 1
  union all select 24, '✉️ وافقوا على الإيميلات',     (count(*) filter (where reminders))::text from public.email_prefs
  union all select 25, '   رفضوا',                    (count(*) filter (where not reminders))::text from public.email_prefs
  union all select 26, '   إيميلات انبعتت آخر ٧ أيام',
                       format('تذكير: %s · بالتوفيق: %s', count(*) filter (where kind = 'comeback'),
                              count(*) filter (where kind = 'exam_eve'))
                       from public.email_log where sent_at > now() - interval '7 days'
  union all select 27, '   رجعوا بعد تذكير',
                       count(distinct l.user_id)::text
                       from public.email_log l join public.app_state s on s.user_id = l.user_id
                       where l.kind = 'comeback' and s.updated_at > l.sent_at
) x
order by 1;

-- استعمال المدرّس (بس إذا الجدول tutor_usage موجود، يعني نشرت دالة المدرّس):
-- select coalesce(sum(count) filter (where day = current_date), 0) as "أسئلة اليوم",
--        coalesce(sum(count) filter (where day > current_date - 7), 0) as "آخر ٧ أيام"
-- from public.tutor_usage;


-- ═══ ٢. يوم بيوم (آخر ٣٠ يوم): تسجيلات، امتحانات، إيميلات ═══
with days as (
  select generate_series((now() at time zone 'Asia/Jerusalem')::date - 29,
                         (now() at time zone 'Asia/Jerusalem')::date, '1 day')::date as d
)
select
  d                                                                                            as "اليوم",
  (select count(*) from auth.users   where (created_at at time zone 'Asia/Jerusalem')::date = d) as "تسجيلات",
  (select count(*) from public.attempts where (created_at at time zone 'Asia/Jerusalem')::date = d) as "امتحانات",
  (select count(*) from public.email_log where (sent_at at time zone 'Asia/Jerusalem')::date = d)  as "إيميلات"
from days
order by d desc;


-- ═══ ٣. الرجوع — يحتاج supabase/activity.sql يكون مشغّل ═══
-- حسب أول يوم فات فيه الطالب: كم رجع تاني يوم، خلال ٣ أيام، خلال أسبوع
with first as (select user_id, min(day) as d0 from public.activity_days group by user_id)
select
  f.d0                                                                                             as "أول يوم",
  count(*)                                                                                         as "طلاب",
  count(*) filter (where exists (select 1 from public.activity_days a
                                 where a.user_id = f.user_id and a.day = f.d0 + 1))                as "رجعوا تاني يوم",
  count(*) filter (where exists (select 1 from public.activity_days a
                                 where a.user_id = f.user_id and a.day between f.d0 + 1 and f.d0 + 3)) as "خلال ٣ أيام",
  count(*) filter (where exists (select 1 from public.activity_days a
                                 where a.user_id = f.user_id and a.day between f.d0 + 1 and f.d0 + 7)) as "خلال أسبوع",
  count(*) filter (where exists (select 1 from public.activity_days a
                                 where a.user_id = f.user_id and a.studied))                       as "درسوا فعلاً"
from first f
group by 1
order by 1 desc;

-- (بديل: كم واحد فات ودرس كل يوم)
-- select day as "اليوم", count(*) as "فاتوا", count(*) filter (where studied) as "درسوا"
-- from public.activity_days group by 1 order by 1 desc;


-- ═══ ٤. أنشط ٣٠ طالب ═══
with meta as (
  select user_id,
    coalesce((data->>'totalReviews')::int, 0) as reviews,
    coalesce((data->>'streak')::int, 0)       as streak,
    case when jsonb_typeof(data->'drills') = 'object'
         then (select count(*) from jsonb_object_keys(data->'drills')) else 0 end as drills
  from public.app_state where key = 'meta'
)
select
  u.email                                                               as "الطالب",
  (u.created_at at time zone 'Asia/Jerusalem')::date                    as "سجّل",
  m.reviews                                                             as "مراجعات",
  m.drills                                                              as "جولات تدريب",
  (select count(*) from public.attempts a where a.user_id = u.id)       as "امتحانات",
  (select max((a.data->>'score')::numeric) from public.attempts a where a.user_id = u.id) as "أعلى علامة",
  m.streak                                                              as "سلسلة",
  (select s.data->>'examDate' from public.app_state s
    where s.user_id = u.id and s.key = 'schedule')                      as "تاريخ الامتحان"
from auth.users u
join meta m on m.user_id = u.id
order by m.reviews + 10 * m.drills + 30 * (select count(*) from public.attempts a where a.user_id = u.id) desc
limit 30;


-- ═══ ٥. أضعف الأقسام بالامتحانات (وين الطلاب بيغلطوا أكثر) ═══
select
  regexp_replace(s.key, '\s*[0-9٠-٩]+\s*$', '')                              as "القسم",
  count(*)                                                                   as "مرات",
  round(100.0 * sum((s.value->>'right')::int) / nullif(sum((s.value->>'total')::int), 0)) || '٪' as "نسبة الصح"
from public.attempts a,
     lateral jsonb_each(a.data->'sections') s
where jsonb_typeof(a.data->'sections') = 'object'
group by 1
order by sum((s.value->>'right')::int)::numeric / nullif(sum((s.value->>'total')::int), 0);


-- ═══ ٦. توزيع العلامات ═══
select
  case when score >= 134 then '4) 134+ פטור'
       when score >= 110 then '3) 110–133'
       when score >= 90  then '2) 90–109'
       else                   '1) أقل من 90' end   as "العلامة",
  count(*)                                         as "امتحانات"
from (select (data->>'score')::numeric as score from public.attempts where data ? 'score') x
group by 1
order by 1;
