# Burmese copy review

Status: **Awaiting native-speaker review.** Reviewer: **the project owner (confirmed in chat on 21 October 2026)**.

All Burmese UI copy is draft, including strings inherited from the previous handoff. The PR remains a draft until the owner records approval or requests corrections. Automated rendering checks do not count as language approval.

Review in context with `index.html`: dispatcher board and navigation, buyer link verification and confirmation, rider next stop, delivery and failure dialogs, and cash handover. Switch the rider to night mode. Check at 390px and with enlarged text. Use the English companion text to verify intended meaning.

For every row, check natural Yangon usage, the meaning of the action, spelling, marks, line breaks, and whether a short label can be mistaken for a completed action. Mark the checkbox only after checking all uses. Record replacement copy in the last column; keep English or suggest an English correction too. Some repeated strings serve different contexts. This inventory contains all distinct Burmese runs in the UI source; adjacent English, amounts and punctuation remain visible in the application.

Pay particular attention to: “Waiting on buyer” (waiting for their response, not a buyer waiting), “Ready to send” (still requires receipt and route checks), “Delivered” (only after cash/handoff is saved), retry vs return, prepaid zero cash, and handover vs cash collection. In-code regex ranges and synthetic order data are excluded from this UI inventory. The parser's own Burmese vocabulary is outside this UI change.

| Checked | Draft Burmese | Context and source line | Correction or approval note |
| --- | --- | --- | --- |
| [ ] | မင်္ဂလာ နံနက်ခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [ ] | မင်္ဂလာ နေ့လယ်ခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [ ] | မင်္ဂလာ ညနေခင်းပါ | `greeting` (`functional-app.js:71`) | |
| [ ] | စစ်ရန် | `LANES` (`functional-app.js:114`) | |
| [ ] | ဝယ်သူ စောင့်ဆဲ | `LANES` (`functional-app.js:114`) | |
| [ ] | ပို့ရန် အသင့် | `LANES` (`functional-app.js:114`) | |
| [ ] | ပို့ဆောင်သူထံ | `LANES` (`functional-app.js:114`) | |
| [ ] | ပို့ပြီး | `LANES` (`functional-app.js:114`), `riderView` (`functional-app.js:161`) | |
| [ ] | အော်ဒါ ကူးထည့် | `nav` (`functional-app.js:119`) | |
| [ ] | ယနေ့ အော်ဒါများ | `nav` (`functional-app.js:119`), `head` (`functional-app.js:130`) | |
| [ ] | ပို့ဆောင်ရေး လမ်းကြောင်း | `nav` (`functional-app.js:119`) | |
| [ ] | ပို့ပြီးပါပြီ | `customerHeading` (`functional-app.js:125`), `result` (`functional-app.js:249`) | |
| [ ] | လာနေပါပြီ | `customerHeading` (`functional-app.js:125`) | |
| [ ] | ပယ်ဖျက်ပြီး | `customerHeading` (`functional-app.js:125`) | |
| [ ] | အသိပေးချက် | `customerHeading` (`functional-app.js:125`) | |
| [ ] | လိပ်စာ အတည်ပြုပါ | `customerHeading` (`functional-app.js:125`) | |
| [ ] | ဂါဝန် အနီ ၁ ထည် | `head` (`functional-app.js:131`) | |
| [ ] | ကမာရွတ်၊ လှည်းတန်း | `head` (`functional-app.js:131`) | |
| [ ] | နောက်ဘက် | `head` (`functional-app.js:131`) | |
| [ ] | လမ်းပြ | `customerHome` (`functional-app.js:152`), `customerView` (`functional-app.js:153`) | |
| [ ] | ပို့ဆောင်မှု လင့်ခ် | `customerHome` (`functional-app.js:152`) | |
| [ ] | လင့်ခ် ပိတ်ထားသည် | `customerView` (`functional-app.js:153`) | |
| [ ] | လင့်ခ် မရနိုင်ပါ | `customerView` (`functional-app.js:153`) | |
| [ ] | ဆက်လုပ်မည် | `customerView` (`functional-app.js:154`) | |
| [ ] | အသံဖြင့်ဖတ် | `riderView` (`functional-app.js:160`) | |
| [ ] | မြေပုံ | `riderView` (`functional-app.js:160`) | |
| [ ] | မပို့နိုင်ပါ | `riderView` (`functional-app.js:161`) | |
| [ ] | ယခုနေရာကို သုံးမည် | `initialLocationForm` (`functional-app.js:170`) | |
| [ ] | ပို့မည် | `initialLocationForm` (`functional-app.js:170`) | |
| [ ] | အတည်ပြုမည် | `customerForm` (`functional-app.js:207`) | |
| [ ] | မလုပ်တော့ပါ | `dialog` (`functional-app.js:221`) | |
| [ ] | ငွေလွှဲအပ်မည် | `d` (`functional-app.js:233`), `result` (`functional-app.js:239`) | |
| [ ] | လွှဲအပ်သည့်ငွေ | `d` (`functional-app.js:233`) | |
| [ ] | ကျပ် | `d` (`functional-app.js:233`), `d` (`functional-app.js:245`) | |
| [ ] | ငွေပမာဏ ကွာခြားရသည့်အကြောင်း | `d` (`functional-app.js:233`), `d` (`functional-app.js:245`) | |
| [ ] | ပို့ပြီးကြောင်း အတည်ပြုမည် | `d` (`functional-app.js:245`) | |
| [ ] | ကောက်ခံရရှိငွေ မှတ်တမ်းတင်မည် | `d` (`functional-app.js:245`) | |
| [ ] | ကောက်ခံရရှိငွေ | `d` (`functional-app.js:245`) | |
| [ ] | မပို့နိုင်သည့်အကြောင်း | `failDialog` (`functional-app.js:252`) | |
| [ ] | အကြောင်းရင်း | `failDialog` (`functional-app.js:252`) | |
| [ ] | ဝယ်သူ ဖုန်းမကိုင်ပါ | `failDialog` (`functional-app.js:252`) | |
| [ ] | အိမ်တွင် မရှိပါ | `failDialog` (`functional-app.js:252`) | |
| [ ] | နေရာ ရှာမတွေ့ပါ | `failDialog` (`functional-app.js:252`) | |
| [ ] | ဝယ်သူ လက်မခံပါ | `failDialog` (`functional-app.js:252`) | |
| [ ] | နောက်တစ်ဆင့် | `failDialog` (`functional-app.js:252`) | |
| [ ] | ယနေ့ ထပ်ပို့မည် | `failDialog` (`functional-app.js:252`) | |
| [ ] | ဂိုဒေါင်သို့ ပြန်ပို့မည် | `failDialog` (`functional-app.js:252`) | |
| [ ] | ထပ်ပို့မည့်အချိန် | `failDialog` (`functional-app.js:252`) | |
| [ ] | မှတ်တမ်းတင်မည် | `failDialog` (`functional-app.js:252`) | |

## Sign-off

- Reviewer: project owner
- Review date: pending
- Approved source commit: pending
- Remaining corrections: pending
- Approval: pending (do not mark ready based on this generated checklist)

After corrections, regenerate source references if lines move, repeat mobile/night checks, and record the exact approved commit. Then mark the PR ready for review.
