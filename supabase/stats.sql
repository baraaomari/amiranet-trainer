-- إحصاءات الموقع — الصقه في: Supabase ← SQL Editor ← New query ← Run
-- للقراءة فقط، لا يغيّر أي بيانات.

-- ═══ نظرة عامة ═══
select
  (select count(*) from auth.users)                                        as "إجمالي المسجّلين",
  (select count(*) from auth.users where last_sign_in_at > now() - interval '7 days')
                                                                           as "دخلوا آخر ٧ أيام",
  (select count(*) from auth.users where created_at > now() - interval '7 days')
                                                                           as "سجّلوا آخر ٧ أيام",
  (select count(distinct user_id) from public.app_state)                    as "بدأوا الاستعمال فعلاً",
  (select count(*) from public.attempts)                                   as "امتحانات مُنجَزة";


-- ═══ التسجيلات يوماً بيوم (آخر ٣٠ يوم) ═══
select
  created_at::date            as "اليوم",
  count(*)                    as "حسابات جديدة"
from auth.users
where created_at > now() - interval '30 days'
group by 1
order by 1 desc;


-- ═══ نشاط المستخدمين ═══
-- «بدأ الاستعمال» = عنده بيانات محفوظة فعلاً، لا مجرّد حساب.
select
  u.email                                                   as "المستخدم",
  u.created_at::date                                        as "سجّل في",
  u.last_sign_in_at::date                                   as "آخر دخول",
  (select count(*) from public.attempts a where a.user_id = u.id)
                                                            as "امتحانات",
  (select count(*) from public.app_state s
     where s.user_id = u.id and s.key like 'srs:%')          as "مستويات بدأها"
from auth.users u
order by u.last_sign_in_at desc nulls last
limit 100;


-- ═══ متوسط العلامات (مؤشّر على جودة الامتحانات) ═══
select
  round(avg((data->>'score')::numeric), 1)  as "متوسط العلامة",
  min((data->>'score')::numeric)            as "أدنى",
  max((data->>'score')::numeric)            as "أعلى",
  count(*)                                  as "عدد المحاولات"
from public.attempts
where data ? 'score';


-- ═══ استهلاك المدرّس اليوم (إن نشرت الدالة) ═══
-- يفيدك لمراقبة ما يُصرف على مفتاح Anthropic.
select
  u.email                       as "المستخدم",
  t.count                       as "أسئلة اليوم"
from public.tutor_usage t
join auth.users u on u.id = t.user_id
where t.day = current_date
order by t.count desc;
