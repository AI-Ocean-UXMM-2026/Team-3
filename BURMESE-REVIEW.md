# Burmese copy review

Status: **Approved by the project owner on 21 October 2026.**

The project owner explicitly approved the Burmese in chat: “Yes burmese review is fine continue on.” This records human approval of the current UI inventory, including inherited strings, against source commit `6b800c48741ec3973378253a1b0b92ae573167d6`. The following Inline/mobile wordmark change does not alter any Burmese strings. Automated rendering checks are separate from this language approval.

Review in context with `index.html`: dispatcher board and navigation, buyer link verification and confirmation, rider next stop, delivery and failure dialogs, and cash handover. Switch the rider to night mode. Check at 390px and with enlarged text. Use the English companion text to verify intended meaning.

For every row, check natural Yangon usage, the meaning of the action, spelling, marks, line breaks, and whether a short label can be mistaken for a completed action. Mark the checkbox only after checking all uses. Record replacement copy in the last column; keep English or suggest an English correction too. Some repeated strings serve different contexts. This inventory contains all distinct Burmese runs in the UI source; adjacent English, amounts and punctuation remain visible in the application.

Pay particular attention to: “Waiting on buyer” (waiting for their response, not a buyer waiting), “Ready to send” (still requires receipt and route checks), “Delivered” (only after cash/handoff is saved), retry vs return, prepaid zero cash, and handover vs cash collection. In-code regex ranges and synthetic order data are excluded from this UI inventory. The parser's own Burmese vocabulary is outside this UI change.

| Checked | Draft Burmese | Context and source line | Correction or approval note |
| --- | --- | --- | --- |
| [x] | မင်္ဂလာ နံနက်ခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [x] | မင်္ဂလာ နေ့လယ်ခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [x] | မင်္ဂလာ ညနေခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [x] | စစ်ရန် | `LANES` (`functional-app.js:114`) | |
| [x] | ဝယ်သူ စောင့်ဆဲ | `LANES` (`functional-app.js:114`) | |
| [x] | ပို့ရန် အသင့် | `LANES` (`functional-app.js:114`) | |
| [x] | ပို့ဆောင်သူထံ | `LANES` (`functional-app.js:114`) | |
| [x] | ပို့ပြီး | `LANES` (`functional-app.js:114`), `riderView` (`functional-app.js:162`) | |
| [x] | အော်ဒါ ကူးထည့် | `nav` (`functional-app.js:120`) | |
| [x] | ယနေ့ အော်ဒါများ | `nav` (`functional-app.js:120`), `head` (`functional-app.js:131`) | |
| [x] | ပို့ဆောင်ရေး လမ်းကြောင်း | `nav` (`functional-app.js:120`) | |
| [x] | ပို့ပြီးပါပြီ | `customerHeading` (`functional-app.js:126`), `result` (`functional-app.js:250`) | |
| [x] | လာနေပါပြီ | `customerHeading` (`functional-app.js:126`) | |
| [x] | ပယ်ဖျက်ပြီး | `customerHeading` (`functional-app.js:126`) | |
| [x] | အသိပေးချက် | `customerHeading` (`functional-app.js:126`) | |
| [x] | လိပ်စာ အတည်ပြုပါ | `customerHeading` (`functional-app.js:126`) | |
| [x] | ဂါဝန် အနီ ၁ ထည် | `head` (`functional-app.js:132`) | |
| [x] | ကမာရွတ်၊ လှည်းတန်း | `head` (`functional-app.js:132`) | |
| [x] | နောက်ဘက် | `head` (`functional-app.js:132`) | |
| [x] | လမ်းပြ | `customerHome` (`functional-app.js:153`), `customerView` (`functional-app.js:153`) | |
| [x] | ပို့ဆောင်မှု လင့်ခ် | `customerHome` (`functional-app.js:153`) | |
| [x] | လင့်ခ် ပိတ်ထားသည် | `customerView` (`functional-app.js:154`) | |
| [x] | လင့်ခ် မရနိုင်ပါ | `customerView` (`functional-app.js:154`) | |
| [x] | ဆက်လုပ်မည် | `customerView` (`functional-app.js:155`) | |
| [x] | အသံဖြင့်ဖတ် | `riderView` (`functional-app.js:161`) | |
| [x] | မြေပုံ | `riderView` (`functional-app.js:161`) | |
| [x] | မပို့နိုင်ပါ | `riderView` (`functional-app.js:162`) | |
| [x] | ယခုနေရာကို သုံးမည် | `initialLocationForm` (`functional-app.js:171`) | |
| [x] | ပို့မည် | `initialLocationForm` (`functional-app.js:171`) | |
| [x] | အတည်ပြုမည် | `customerForm` (`functional-app.js:208`) | |
| [x] | မလုပ်တော့ပါ | `dialog` (`functional-app.js:222`) | |
| [x] | ငွေလွှဲအပ်မည် | `d` (`functional-app.js:234`), `result` (`functional-app.js:240`) | |
| [x] | လွှဲအပ်သည့်ငွေ | `d` (`functional-app.js:234`) | |
| [x] | ကျပ် | `d` (`functional-app.js:234`), `d` (`functional-app.js:246`) | |
| [x] | ငွေပမာဏ ကွာခြားရသည့်အကြောင်း | `d` (`functional-app.js:234`), `d` (`functional-app.js:246`) | |
| [x] | ပို့ပြီးကြောင်း အတည်ပြုမည် | `d` (`functional-app.js:246`) | |
| [x] | ကောက်ခံရရှိငွေ မှတ်တမ်းတင်မည် | `d` (`functional-app.js:246`) | |
| [x] | ကောက်ခံရရှိငွေ | `d` (`functional-app.js:246`) | |
| [x] | မပို့နိုင်သည့်အကြောင်း | `failDialog` (`functional-app.js:253`) | |
| [x] | အကြောင်းရင်း | `failDialog` (`functional-app.js:253`) | |
| [x] | ဝယ်သူ ဖုန်းမကိုင်ပါ | `failDialog` (`functional-app.js:253`) | |
| [x] | အိမ်တွင် မရှိပါ | `failDialog` (`functional-app.js:253`) | |
| [x] | နေရာ ရှာမတွေ့ပါ | `failDialog` (`functional-app.js:253`) | |
| [x] | ဝယ်သူ လက်မခံပါ | `failDialog` (`functional-app.js:253`) | |
| [x] | နောက်တစ်ဆင့် | `failDialog` (`functional-app.js:253`) | |
| [x] | ယနေ့ ထပ်ပို့မည် | `failDialog` (`functional-app.js:253`) | |
| [x] | ဂိုဒေါင်သို့ ပြန်ပို့မည် | `failDialog` (`functional-app.js:253`) | |
| [x] | ထပ်ပို့မည့်အချိန် | `failDialog` (`functional-app.js:253`) | |
| [x] | မှတ်တမ်းတင်မည် | `failDialog` (`functional-app.js:253`) | |

## Sign-off

- Reviewer: project owner
- Review date: 21 October 2026
- Approved source commit: `6b800c48741ec3973378253a1b0b92ae573167d6`
- Remaining corrections: none requested by the reviewer
- Approval: explicitly given by the project owner in chat

Any future Burmese wording changes need another review. Refresh source references if lines move and repeat rendering checks after UI changes.

## Added 21 Oct 2026 (needs native review)
- Page signs: ဝယ်သူ လင့်ခ်များ (Buyer links), ငွေစာရင်း ပိတ်ရန် (Hub close-out), စစ်ရန် အော်ဒါများ (Exceptions), အော်ဒါ တစ်ခု ထည့်ရန် (Add one order)
- Rider undo: ပြန်ဖျက်မည် (Undo); rider toasts in the `MY` map in frontend/js/functional-app.js

## Delivery day and time slots (buyer page)

| Burmese | English meaning | Where |
| --- | --- | --- |
| ပို့ရမည့်နေ့ | Delivery day | Buyer page, day cards heading |
| အချိန်ရွေးချယ်ပါ | Choose a time (Preferred time) | Buyer page, slot cards heading |
| မနက် | Morning (10:00–12:00) | Slot card |
| နေ့လည် | Afternoon (14:00–16:00) | Slot card |
| ညနေ | Evening (16:00–18:00) | Slot card |
| အချိန်မရွေး | Any time | Slot card |
| သိမ်းပြီးပါပြီ | Saved (your answer is saved) | Buyer page, saved answer card |
| ပြင်မည် | Edit (my answer) | Buyer page, Edit button |

## Added 22 Oct 2026: sign-in, sign-out and accept alerts (needs native review)

| Burmese | English meaning | Where |
| --- | --- | --- |
| လိပ်စာလည်းမှန် အချိန်လည်းမှန် | Right address, right time (motto, given by the project owner) | Both sign-in pages |
| ပို့ဆောင်သူ | Rider | Rider sign-in role chip; buyer text-message banner |
| ဝင်ရောက်ရန် | Sign in (page title) | Rider sign-in |
| ပထမဆုံးအကြိမ် | First time here | Rider invite-code view |
| ဖိတ်ခေါ်ကုဒ် | Invite code | Rider invite-code view |
| ဖုန်းနံပါတ် | Phone number | Rider sign-in, shop account form |
| လျှို့ဝှက်နံပါတ် ၄ လုံး | 4-digit PIN | Rider sign-in |
| ဝင်မည် / ဆက်လုပ်မည် | Sign in / Continue (button) | Rider sign-in |
| ဆိုင်အမည် | Shop name | Create shop account |
| ဖုန်း / အီးမေးလ် | Phone or email | Dispatcher sign-in |
| စကားဝှက် | Password | Dispatcher sign-in |
| ထွက်မည် | Sign out | Rider menu |
| ဤဖုန်းမှ ထွက်မည်လား | Sign out of this phone? | Rider sign-out confirm |
| ပို့ဆောင်သူ {name} က သင့်ပါဆယ် {ref} ကို လက်ခံပြီးပါပြီ။ | Rider {name} accepted your parcel {ref}. | Buyer text-message banner |
| သင့်ဆီ ရောက်လာတော့မည် | You're the next stop (wording given by the project owner) | Buyer page heading when the rider's next stop is the buyer |
