# Discovery meeting: Lone Star Foodservice (simulated)

> **Simulated.** Lone Star Foodservice, its people, systems and numbers are invented
> for this example. This file is written to look like the export of an AI note taker.

**Meeting:** Modernization discovery, 30 minutes booked, video call
**Attendees:**
- Dana Whitfield, CIO, Lone Star Foodservice
- Marcus Reyes, Director of Data, Lone Star Foodservice
- Angela Brooks, Enterprise Architect, Lone Star Foodservice
- Lead architect, modernization partner (facilitating)

**Recording:** consent given by all attendees at 00:00:20

---

**[00:01:05] Lead architect:** Thanks for the time. I'd like to understand what's driving this, what's in scope, and what you'd need to see in three weeks to decide on a bigger program.

**[00:01:30] Dana Whitfield:** We distribute food to about four thousand restaurants, schools and government kitchens across Texas and the Southwest. Order entry still runs on the mainframe. Sales wants to change prices weekly to respond to suppliers. Today a pricing change takes a six-week release.

**[00:02:40] Dana Whitfield:** And two of the three people who understand that COBOL retire within two years. That's the risk that keeps me up at night.

**[00:03:15] Lead architect:** Which applications are on the table?

**[00:03:30] Angela Brooks:** Five. ORDER-ENTRY on the mainframe, which includes the pricing program, ORDPRICE. HR-REPORTS, old Crystal Reports. CLAIMS-PORTAL, where customers file credit claims for damaged deliveries, a Java app on WebLogic. PRICING-ENGINE, which we rebuilt in Go on Kubernetes two years ago. And DOC-ARCHIVE, a .NET app on VMs in our data center.

**[00:04:50] Angela Brooks:** The data center lease ends in nine months. Whatever is still in there has to go somewhere.

**[00:05:20] Lead architect:** Do you already have a view on what happens to each one?

**[00:05:35] Angela Brooks:** Opinions, not a decision. I'd like a recommendation for each with the reasoning, and I want to review every one before it goes anywhere. I've seen AI tools produce confident nonsense.

**[00:06:10] Lead architect:** Agreed. The agent recommends, you decide. Every recommendation comes with its reason, and nothing is final until you sign it off.

**[00:07:00] Dana Whitfield:** On ORDER-ENTRY specifically, I don't want a translation of the COBOL. I want to know what the pricing rules actually are. Nobody has written them down since 2003.

**[00:07:20] Dana Whitfield:** There's a volume discount someone added in 2003, from a pricing memo, PM-114. I honestly don't know if it's still policy.

**[00:07:40] Lead architect:** Then the first step is rule extraction. The agent reads ORDPRICE and writes down every business rule, each one pointing at the source lines that prove it. Then it writes parity tests: cases the new system has to pass to behave exactly like the old one.

**[00:08:20] Angela Brooks:** Who decides what the right answer is for those tests? Not the AI, I hope.

**[00:08:35] Lead architect:** The legacy program does. Expected results come from running the COBOL, never from the model. If the model's prediction and the legacy result disagree, that goes to a person.

**[00:09:30] Marcus Reyes:** If ORDER-ENTRY moves, the customer master moves with it. CUSTMAST. About two hundred thousand customer accounts. Balances are stored in cents, names are LAST comma FIRST in capitals, dates are eight-digit strings. Every migration I've seen goes wrong on exactly those details.

**[00:09:55] Lead architect:** Does anything else read CUSTMAST besides ORDER-ENTRY?

**[00:10:05] Marcus Reyes:** Billing, at least. Maybe more. I'll check.

**[00:10:15] Marcus Reyes:** I won't sign off a migration that doesn't reconcile to our end-of-day control report. Row counts, total balances, status counts. If those don't tie, it doesn't ship.

**[00:10:50] Lead architect:** Then reconciliation is the exit gate. The agent proposes the mapping, the harness migrates the rows and compares them with your control report, and the mapping can't be submitted until it ties.

**[00:11:40] Marcus Reyes:** And no customer personal data goes to an AI model. Security will stop the project on that alone.

**[00:12:00] Lead architect:** The agent will see the schema and a couple of masked sample rows, never the table. It picks from a fixed list of tested transforms rather than writing code that touches your data.

**[00:13:10] Dana Whitfield:** What does this cost to run? I don't want a science project with an open-ended cloud bill.

**[00:13:30] Lead architect:** Every model call is priced and logged, and each run has a budget cap that is checked before every call. The POC report will show the cost per run.

**[00:14:20] Angela Brooks:** I'll also need to see what the agents actually did. If something goes wrong I want the trail.

**[00:14:35] Lead architect:** Every step is recorded: which agent ran, what it was given, what it returned, how many tokens. You'll be able to read a run as a tree.

**[00:15:30] Angela Brooks:** And it runs in our Google Cloud project, not somewhere else.

**[00:15:45] Lead architect:** Understood. We'd deploy it as a job in your project, with model access through your cloud account. For the POC we'd use synthetic or masked data only.

**[00:16:20] Angela Brooks:** Security will want a say on that route: the model provider's own API, or Claude through Vertex AI in our project. I'll get you an answer.

**[00:17:00] Dana Whitfield:** In three weeks I want three things. A recommendation for each of the five applications. The ORDPRICE rules written down with tests. And proof that CUSTMAST can move without losing a cent. If I get that, I take a funded program to the board in January.

**[00:18:10] Lead architect:** Then those are the success criteria. I'll send a recap today with the requirements numbered, so you can correct anything before we start.

**[00:18:40] Marcus Reyes:** I can send a CUSTMAST extract, masked, and last night's control report by Friday.

**[00:19:00] Angela Brooks:** I'll send the ORDPRICE source and the application inventory.

**[00:19:20] Dana Whitfield:** Good. Let's go.

---
*End of transcript. 19 minutes 25 seconds of discussion captured.*
