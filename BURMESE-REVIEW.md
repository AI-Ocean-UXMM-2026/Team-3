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
| [ ] | ပို့ပြီး | `LANES` (`functional-app.js:114`), `riderView` (`functional-app.js:162`) | |
| [ ] | အော်ဒါ ကူးထည့် | `nav` (`functional-app.js:120`) | |
| [ ] | ယနေ့ အော်ဒါများ | `nav` (`functional-app.js:120`), `head` (`functional-app.js:131`) | |
| [ ] | ပို့ဆောင်ရေး လမ်းကြောင်း | `nav` (`functional-app.js:120`) | |
| [ ] | ပို့ပြီးပါပြီ | `customerHeading` (`functional-app.js:126`), `result` (`functional-app.js:250`) | |
| [ ] | လာနေပါပြီ | `customerHeading` (`functional-app.js:126`) | |
| [ ] | ပယ်ဖျက်ပြီး | `customerHeading` (`functional-app.js:126`) | |
| [ ] | အသိပေးချက် | `customerHeading` (`functional-app.js:126`) | |
| [ ] | လိပ်စာ အတည်ပြုပါ | `customerHeading` (`functional-app.js:126`) | |
| [ ] | ဂါဝန် အနီ ၁ ထည် | `head` (`functional-app.js:132`) | |
| [ ] | ကမာရွတ်၊ လှည်းတန်း | `head` (`functional-app.js:132`) | |
| [ ] | နောက်ဘက် | `head` (`functional-app.js:132`) | |
| [ ] | လမ်းပြ | `customerHome` (`functional-app.js:153`), `customerView` (`functional-app.js:153`) | |
| [ ] | ပို့ဆောင်မှု လင့်ခ် | `customerHome` (`functional-app.js:153`) | |
| [ ] | လင့်ခ် ပိတ်ထားသည် | `customerView` (`functional-app.js:154`) | |
| [ ] | လင့်ခ် မရနိုင်ပါ | `customerView` (`functional-app.js:154`) | |
| [ ] | ဆက်လုပ်မည် | `customerView` (`functional-app.js:155`) | |
| [ ] | အသံဖြင့်ဖတ် | `riderView` (`functional-app.js:161`) | |
| [ ] | မြေပုံ | `riderView` (`functional-app.js:161`) | |
| [ ] | မပို့နိုင်ပါ | `riderView` (`functional-app.js:162`) | |
| [ ] | ယခုနေရာကို သုံးမည် | `initialLocationForm` (`functional-app.js:171`) | |
| [ ] | ပို့မည် | `initialLocationForm` (`functional-app.js:171`) | |
| [ ] | အတည်ပြုမည် | `customerForm` (`functional-app.js:208`) | |
| [ ] | မလုပ်တော့ပါ | `dialog` (`functional-app.js:222`) | |
| [ ] | ငွေလွှဲအပ်မည် | `d` (`functional-app.js:234`), `result` (`functional-app.js:240`) | |
| [ ] | လွှဲအပ်သည့်ငွေ | `d` (`functional-app.js:234`) | |
| [ ] | ကျပ် | `d` (`functional-app.js:234`), `d` (`functional-app.js:246`) | |
| [ ] | ငွေပမာဏ ကွာခြားရသည့်အကြောင်း | `d` (`functional-app.js:234`), `d` (`functional-app.js:246`) | |
| [ ] | ပို့ပြီးကြောင်း အတည်ပြုမည် | `d` (`functional-app.js:246`) | |
| [ ] | ကောက်ခံရရှိငွေ မှတ်တမ်းတင်မည် | `d` (`functional-app.js:246`) | |
| [ ] | ကောက်ခံရရှိငွေ | `d` (`functional-app.js:246`) | |
| [ ] | မပို့နိုင်သည့်အကြောင်း | `failDialog` (`functional-app.js:253`) | |
| [ ] | အကြောင်းရင်း | `failDialog` (`functional-app.js:253`) | |
| [ ] | ဝယ်သူ ဖုန်းမကိုင်ပါ | `failDialog` (`functional-app.js:253`) | |
| [ ] | အိမ်တွင် မရှိပါ | `failDialog` (`functional-app.js:253`) | |
| [ ] | နေရာ ရှာမတွေ့ပါ | `failDialog` (`functional-app.js:253`) | |
| [ ] | ဝယ်သူ လက်မခံပါ | `failDialog` (`functional-app.js:253`) | |
| [ ] | နောက်တစ်ဆင့် | `failDialog` (`functional-app.js:253`) | |
| [ ] | ယနေ့ ထပ်ပို့မည် | `failDialog` (`functional-app.js:253`) | |
| [ ] | ဂိုဒေါင်သို့ ပြန်ပို့မည် | `failDialog` (`functional-app.js:253`) | |
| [ ] | ထပ်ပို့မည့်အချိန် | `failDialog` (`functional-app.js:253`) | |
| [ ] | မှတ်တမ်းတင်မည် | `failDialog` (`functional-app.js:253`) | |

## Sign-off

- Reviewer: project owner
- Review date: pending
- Approved source commit: pending
- Remaining corrections: pending
- Approval: pending (do not mark ready based on this generated checklist)

After corrections, regenerate source references if lines move, repeat mobile/night checks, and record the exact approved commit. Then mark the PR ready for review.
