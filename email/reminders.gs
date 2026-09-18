/**
 * مدرّب أميرنت — تذكيرات الإيميل (Google Apps Script)
 *
 * يشتغل مجاناً من حساب Gmail الخاص بالموقع (~١٠٠ إيميل باليوم). الرسائل بتنبعت من
 * سيرفرات جوجل نفسها، فبتوصل للبريد الوارد. الخطوات كاملة في EMAIL.md.
 *
 * Script Properties (⚙ Project Settings ← Script Properties):
 *   SUPABASE_URL       https://xxxx.supabase.co
 *   SUPABASE_ANON_KEY  المفتاح العام (anon) — مش service_role
 *   REMINDER_SECRET    select value from private.settings where key = 'reminder_secret';
 *   SITE_URL           https://amiranet-trainer.netlify.app
 *
 * الدوال الي بتشغّلها بإيدك:
 *   sendTestToMe()  إيميلين تجربة لإلك إنت، بدون ما يلمس قاعدة البيانات
 *   dryRun()        مين كان رح يوصله إيميل هلق — بدون إرسال
 *   setup()         تشغيل يومي الساعة ٦ المسا بتوقيت القدس (مرة وحدة)
 */

const PROPS = PropertiesService.getScriptProperties();

function prop(key) {
  const v = PROPS.getProperty(key);
  if (!v) throw new Error('Missing script property: ' + key + ' (see EMAIL.md)');
  return v;
}

/* ═══════════ التشغيل اليومي ═══════════ */

function sendReminders() {
  const base = ScriptApp.getService().getUrl();
  if (!base) throw new Error('Deploy the script as a web app first (EMAIL.md) — every email needs an unsubscribe link.');

  const list = rpc('reminder_candidates', {}) || [];
  let sent = 0, failed = 0;
  for (const u of list) {
    if (MailApp.getRemainingDailyQuota() < 1) {
      console.warn('Daily Gmail quota reached — the rest will be picked up tomorrow.');
      break;
    }
    try {
      const mail = compose(u, base);
      MailApp.sendEmail({ to: u.email, subject: mail.subject, htmlBody: mail.html, body: mail.text, name: mail.from });
      rpc('log_reminder', { p_user: u.user_id, p_kind: u.kind, p_exam: u.exam_date });
      sent++;
    } catch (e) {
      failed++;
      console.error('Failed for ' + u.user_id + ': ' + e);
    }
  }
  console.log('Candidates: ' + list.length + ' · sent: ' + sent + ' · failed: ' + failed);
}

function setup() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'sendReminders')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('sendReminders').timeBased().everyDays(1).atHour(18).inTimezone('Asia/Jerusalem').create();
  console.log('Daily trigger set: sendReminders at 18:00 Asia/Jerusalem.');
}

function dryRun() {
  const list = rpc('reminder_candidates', {}) || [];
  list.forEach(u => console.log(u.kind + ' · ' + u.email + ' · days left: ' + (u.days_left == null ? '—' : u.days_left)));
  console.log(list.length + ' would be emailed now. Nothing was sent.');
}

function sendTestToMe() {
  const me = Session.getEffectiveUser().getEmail();
  const base = ScriptApp.getService().getUrl() || prop('SITE_URL');
  const sample = { user_id: '00000000-0000-0000-0000-000000000000', email: me, name: null, lang: 'ar', exam_date: null };
  [Object.assign({}, sample, { kind: 'comeback', days_left: 12 }),
   Object.assign({}, sample, { kind: 'exam_eve', days_left: 1 })].forEach(u => {
    const mail = compose(u, base);
    MailApp.sendEmail({ to: me, subject: '[تجربة] ' + mail.subject, htmlBody: mail.html, body: mail.text, name: mail.from });
  });
  console.log('Sent 2 test emails to ' + me);
}

/* ═══════════ رابط إلغاء الاشتراك ═══════════ */

function doGet(e) {
  const p = (e && e.parameter) || {};
  let ok = false;
  if (/^[0-9a-f-]{36}$/i.test(p.u || '') && p.t === sign(p.u)) {
    try { rpc('unsubscribe_reminders', { p_user: p.u }); ok = true; }
    catch (err) { console.error(err); }
  }
  const msg = ok
    ? 'تم إلغاء تذكيرات الإيميل. بتقدر ترجّعها بأي وقت من صفحة الجدول بالموقع.<br><br>Email reminders are turned off. You can turn them back on from the Planner page.'
    : 'الرابط مش صالح أو صار فيه خطأ. جرّب كمان مرة، أو أوقف التذكيرات من صفحة الجدول بالموقع.<br><br>This link is invalid. You can also turn reminders off from the Planner page.';
  return HtmlService.createHtmlOutput(
    '<div style="font-family:Tahoma,Arial,sans-serif;max-width:480px;margin:60px auto;padding:0 20px;text-align:center;line-height:1.9">' +
    '<div style="font-size:40px">📚</div><p>' + msg + '</p></div>'
  ).setTitle('مدرّب أميرنت');
}

function sign(userId) {
  const raw = Utilities.computeHmacSha256Signature(userId, prop('REMINDER_SECRET'));
  return Utilities.base64EncodeWebSafe(raw).replace(/=+$/, '');
}

/* ═══════════ Supabase ═══════════ */

function rpc(fn, args) {
  const key = prop('SUPABASE_ANON_KEY');
  const res = UrlFetchApp.fetch(prop('SUPABASE_URL').replace(/\/$/, '') + '/rest/v1/rpc/' + fn, {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(Object.assign({ p_secret: prop('REMINDER_SECRET') }, args)),
    headers: { apikey: key, Authorization: 'Bearer ' + key },
    muteHttpExceptions: true
  });
  const code = res.getResponseCode(), text = res.getContentText();
  if (code >= 300) throw new Error(fn + ' → HTTP ' + code + ': ' + text);
  return text ? JSON.parse(text) : null;
}

/* ═══════════ نص الرسائل ═══════════ */

function compose(u, base) {
  const en = u.lang === 'en';
  const site = prop('SITE_URL');
  const unsub = base + '?u=' + encodeURIComponent(u.user_id) + '&t=' + sign(u.user_id);
  const hi = u.name ? (en ? 'Hi ' + u.name + ',' : 'أهلاً ' + u.name + '،') : (en ? 'Hi,' : 'أهلاً،');
  const d = u.days_left;
  let subject, paras, tips = [], closing = '', cta;

  if (u.kind === 'exam_eve') {
    subject = en ? 'Your Amiranet exam is tomorrow — good luck! 🍀' : 'بكرا امتحان أميرنت — بالتوفيق! 🍀';
    paras = [en ? 'Tomorrow is the big day. A few last tips:' : 'بكرا يومك الكبير. كم نصيحة أخيرة:'];
    tips = en ? [
      'Sleep well tonight — late-night cramming hurts more than it helps.',
      'Each section has its own timer, and when it ends you cannot go back. Don\'t get stuck on one question.',
      'Restatement: pick the sentence with exactly the same meaning — nothing added, nothing exaggerated.',
      'Reading: go back to the line the question mentions before you answer.'
    ] : [
      'نام منيح الليلة؛ السهر على المراجعة بيضرّ أكثر ما بيفيد.',
      'كل قسم إله وقته، ولما يخلص ما بتقدر ترجع — فلا تعلق على سؤال واحد.',
      'بإعادة الصياغة: اختار الجملة الي بتحكي نفس المعنى بالضبط، بلا زيادة ولا مبالغة.',
      'بالفهم المقروء: ارجع للسطر المذكور بالسؤال قبل ما تجاوب.'
    ];
    closing = en ? 'We\'re with you. Good luck! 💪' : 'إحنا معك. بالتوفيق 💪';
    cta = en ? 'A light last review' : 'مراجعة أخيرة خفيفة';
  } else {
    subject = d != null
      ? (en ? d + ' days until your Amiranet exam' : 'ضايلك ' + daysAr(d) + ' لامتحان أميرنت')
      : (en ? 'Ten minutes of practice today?' : 'اشتقنالك! عشر دقايق دراسة اليوم؟');
    paras = en ? [
      'It\'s been a few days since you last studied.',
      d != null ? 'Your exam is in ' + d + ' days — every study day counts.' : null,
      'Try just ten minutes: one round of words and one practice round.'
    ] : [
      'صارلك كم يوم ما فتت تدرس.',
      d != null ? 'امتحانك بعد ' + daysAr(d) + '، وكل يوم دراسة بيفرق.' : null,
      'جرّب عشر دقايق بس: جولة كلمات وجولة تدريب وحدة.'
    ];
    paras = paras.filter(Boolean);
    cta = en ? 'Continue studying' : 'ارجع ادرس';
  }

  return {
    from: en ? 'Amiranet Trainer' : 'مدرّب أميرنت',
    subject: subject,
    html: layout(en, hi, paras, tips, closing, cta, site, unsub),
    text: [hi].concat(paras, tips.map(x => '• ' + x), closing ? [closing] : [],
                      ['', cta + ': ' + site, '', (en ? 'Unsubscribe: ' : 'إلغاء التذكيرات: ') + unsub]).join('\n')
  };
}

function layout(en, hi, paras, tips, closing, cta, site, unsub) {
  const dir = en ? 'ltr' : 'rtl', side = en ? 'left' : 'right';
  return '<div dir="' + dir + '" style="background:#F1F2F4;padding:24px 12px;font-family:Tahoma,Arial,sans-serif">' +
    '<div style="max-width:520px;margin:0 auto;background:#ffffff;border-radius:20px;padding:28px 24px;' +
      'text-align:' + side + ';color:#15171B;line-height:1.8;font-size:15px">' +
      '<div style="font-size:28px">📚</div>' +
      '<p style="margin:8px 0 12px;font-weight:bold">' + esc(hi) + '</p>' +
      paras.map(p => '<p style="margin:0 0 10px">' + esc(p) + '</p>').join('') +
      (tips.length ? '<ul style="margin:0 0 12px;padding-' + side + ':20px">' +
        tips.map(x => '<li style="margin-bottom:6px">' + esc(x) + '</li>').join('') + '</ul>' : '') +
      (closing ? '<p style="margin:0 0 6px">' + esc(closing) + '</p>' : '') +
      '<p style="margin:22px 0 0"><a href="' + esc(site) + '" style="display:inline-block;background:#15171B;color:#ffffff;' +
        'text-decoration:none;padding:12px 24px;border-radius:999px;font-weight:bold">' + esc(cta) + '</a></p>' +
    '</div>' +
    '<p style="max-width:520px;margin:14px auto 0;text-align:center;font-size:12px;color:#8B9097">' +
      (en ? 'You get this because you turned on email reminders. ' : 'وصلك هاد الإيميل لأنك فعّلت تذكيرات الإيميل. ') +
      '<a href="' + esc(unsub) + '" style="color:#8B9097">' + (en ? 'Unsubscribe' : 'إلغاء التذكيرات') + '</a></p>' +
  '</div>';
}

/* ١ ← يوم واحد، ٢ ← يومين، ٣–١٠ ← أيام، غير هيك ← يوم */
function daysAr(n) {
  if (n === 1) return 'يوم واحد';
  if (n === 2) return 'يومين';
  const digits = String(n).replace(/\d/g, x => '٠١٢٣٤٥٦٧٨٩'[x]);
  return digits + (n >= 3 && n <= 10 ? ' أيام' : ' يوم');
}

function esc(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
