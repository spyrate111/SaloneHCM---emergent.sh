"""Krio narrations for the 7 training videos — same scene order as scenes.py.
Written in accessible Salone Krio with anglicized spelling for natural TTS."""

KRIO = {
    "getting-started": [
        "Kusheh en welkom to SaloneHCM — na Salone yon platform for manage workman den en pay salary. Insai dis first lesson, wi go sign in for di first time, waka round di dashboard, learn usai everything de, en show yu aw for find all di feature dem wey yu get. Mek wi start.",
        "Dis na di sign-in page. Put di work email en password wey yu administrator don gi yu. If yu organisation don turn on two-factor authentication, den go ask yu for one six digit code from yu authenticator app. Now watch as wi sign in as system administrator.",
        "En dis na yu dashboard — di heart of SaloneHCM. Na di top yu go see live numbers: aw much workman den de, aw much di monthly payroll de cost, leave request dem wey de wait, en compliance status. Everything de update real time as yu team de work.",
        "Na di left side na di navigation sidebar. E de show only di module dem wey yu role en yu organisation plan don unlock — so wetin yu see na wetin yu able use. Core H R de na top, payroll en finance de follow am, den administration tools.",
        "Yu no sure usai something de? Open di Feature Directory. All di module dem insai di platform de list ya, group by wetin den de do, with simple explanation en live status — available, need bigger plan, or na only administrator able go de. Click any available card for jump go direct.",
        "Last thing, memba two things: yu settings page na usai yu change yu password en two-factor security, en di Training Center — usai yu find dis video — get quick reference card, knowledge base article, en certification quiz for every role. Yu ready for explore now.",
    ],
    "administrator-guide": [
        "Kusheh en welkom to di SaloneHCM administrator guide. As administrator, na yu de control who able enter di system, wetin den able do, en aw yu organisation set up. Insai di next few minutes wi go cover user management, role flags, organisation settings, branch office dem, en di audit log.",
        "Mek wi start with users en access. From ya yu de invite new user dem by email, reset password, en remove account wey nobody no de use again. Look di role pill dem near every name — admin, employee, en special capability flags.",
        "Two flags important bad for money matter. Di Finance Officer flag mek one user able review en approve payroll voucher. Di M o F approver flag mek den able sign payroll run en authorize voucher payment. Yu de grant den with one click na di banknote icon — en memba: di system enforce separation of duties by itself, so no one person no able push money out alone.",
        "Under settings yu de manage yu organisation profile, yu subscription tier, integration dem like S M S en email, security policy dem like two-factor authentication, en di public transparency portal for government tenant dem.",
        "If yu organisation de submit payroll voucher from plenty branch, district, or ministry, na ya yu de define den office. Every branch get in own unique code, optional ministry link, en one branch supervisor wey in approval need before dat branch in voucher reach headquarters. Yu able assign workman den to den branch from dis same screen.",
        "Last one, di audit log. Every sensitive action insai SaloneHCM — every approval, every change, every payment authorization — de record ya with who do am en when. If regulator or di Auditor General ask, di answer na one search away.",
        "Dat na di administrator essentials: control access tight, grant money power careful, keep yu settings current, en mek di audit log memba everything for yu. Go take di administrator certification quiz na di Training Center for confirm wetin yu sabi.",
    ],
    "hr-officer-training": [
        "Kusheh en welkom to H R officer training for SaloneHCM. Na yu work de keep every record correct — en correct record na wetin de mek payroll, compliance, en audit easy. Wi go cover di employee register, leave management, attendance, en di document vault.",
        "Di employee register na yu single source of truth. Every person in grade, salary, bank details, NASSIT number, en department de live ya. Use di search bar for find anybody one time, en di add employee button for onboard new person — di form go guide yu through every required field, including statutory identifier dem.",
        "Next one, leave. Workman den de request leave from den self-service portal, en di request dem de come ya for yu approval. Yu able see balance, date dem wey de overlap, en di team calendar before yu decide — so cover gap no go surprise yu.",
        "Attendance de gi yu di daily picture: who clock in, who no come, en di timesheet total dem wey de feed into payroll. H R able correct record when device fail — en every correction de audit log.",
        "Last one, di document vault. Contract dem, identity document dem, disciplinary letter dem — upload one time, store safe na di cloud, en scope to yu organisation. Use di search en category filter for find anything quick quick.",
        "Memba: clean employee data today de prevent payroll palava tomorrow. When yu ready, go take di H R officer quiz na di Training Center en get yu certificate.",
    ],
    "payroll-officer-training": [
        "Kusheh en welkom to payroll officer training. Na ya salary de turn to payment — correct, on time, en fully compliant with Salone tax law. Wi go run payroll preview, understand di gross-to-net calculation, export payslip en bank file dem, en look statutory compliance.",
        "Dis na di payroll page. Pick di month en year, den always preview before yu run. Di preview de calculate every workman in gross pay, apply di N R A progressive P A Y E band dem, remove di five percent NASSIT employee contribution, apply any loan repayment — en show yu di exact net pay, en nothing no commit yet.",
        "When di preview look correct, di run button de commit am. For government tenant dem, SaloneHCM go first check di budget for di period, respect di payroll cut-off lock, en send di run go di Ministry of Finance approval chain — usai di required number of different signature dem must collect before di run approve.",
        "Every completed run de show na di history below. From de yu de download individual payslip P D F dem, send bulk payslip S M S message, en generate bank disbursement file na Rokel, S L C B, U B A, or Ecobank format — ready for upload go yu bank portal.",
        "Di compliance page de track yu statutory obligation dem: monthly P A Y E return to di N R A en NASSIT contribution schedule dem. SaloneHCM de generate di export na di exact expected format — pick di period, generate, en file. Di deadline dem de track so nothing no go pass yu.",
        "Di golden rule dem: preview before yu run, no ever bypass blocked budget check, en file yu return before di deadline. Go take di payroll officer quiz na di Training Center for certify yu skill.",
    ],
    "vouchers-deep-dive": [
        "Kusheh en welkom to di payroll voucher deep-dive. Before SaloneHCM, branch dem been de email spreadsheet or carry paper voucher go headquarters. Now, every branch de submit into one central digital repository, en every voucher de pass one strict approval chain before even one leone move. Mek wi waka di full journey.",
        "Dis na di central repository. Di indicator card dem de show aw much branch don submit dis period, wetin de wait supervisor sign-off, wetin de na finance review, en wetin don authorize for payment. Di filter dem mek yu able slice by period, branch, en workflow stage.",
        "Open any voucher en yu go see di full story: every employee line with gross pay, P A Y E, NASSIT, loan deduction en net pay; di total dem; en di complete audit timeline — who create am, who approve am, en exactly when. Once e submit, di voucher don freeze. Nobody no able quietly change any number.",
        "Di workflow de enforce four eyes minimum. Branch officer submit. Di branch supervisor approve. Finance officer review en approve — en di system de physically block anybody from approve voucher wey den den self create. Finally one Ministry of Finance approver de authorize payment — en dat person must different from both di creator en di finance approver. Dual control, wey software de enforce, no be trust.",
        "Mistake de happen. Instead of edit in place, reviewer de return di voucher with written reason — at least ten character, e de always record. Di branch correct di figure dem, resubmit, en di revision number go up. Di correction history de permanent.",
        "En di quiet protection dem: one voucher per branch per period — duplicate de reject. One employee no able show na two voucher for di same month — dat na di double-pay guard. En once payment authorize, di voucher turn permanent immutable record. Na so payroll fraud loophole dem de close.",
        "Submit digital, approve na chain, return with reason, en mek di rails do den work. Di voucher certification quiz de wait yu na di Training Center.",
    ],
    "employee-self-service": [
        "Kusheh en welkom to SaloneHCM employee self-service training. Dis short session go show yu everything wey yu able do by yuself — see yu payslip dem, request leave, record attendance, en check yu details — without wait na line na di H R office.",
        "Sign in with di work email en password wey H R gi yu. If yu forget yu password, yu administrator able reset am quick quick. Mek wi sign in as Joseph, one civil servant.",
        "Di self-service page na yu home. Yu payslip dem de list with gross pay, deduction dem, en net pay for every month. Open any one for see di full breakdown — yu P A Y E tax, yu NASSIT contribution, any loan repayment — en download di P D F for yu record or bank loan application.",
        "Yu need time off? Go leave, press new request, pick yu date dem en leave type, den submit. Yu manager go know one time, en yu able watch di status change from pending to approved right ya. Yu remaining balance de always show, so no guessing game no de.",
        "Na di attendance page yu de clock in en out, en review yu own history. If something look wrong — like missed clock-out — tell yu H R officer en den able correct am, en di correction de log.",
        "Na dat — payslip, leave, en attendance, all na yu own hand. If yu no sure about anything, di Training Center get quick reference card wey den make just for employee dem. Tenki for watch.",
    ],
    "gov-modules-tour": [
        "Kusheh en welkom to di government modules tour. SaloneHCM in Gov tier de add di control dem wey public payroll demand: civil service salary structure, establishment discipline, budget check before money move, en public transparency. Mek wi tour each one.",
        "Di civil service module de hold yu grade en step salary matrix, allowance rule dem, en budget code dem. Salary de flow from di structure — no be from ad-hoc number — so grade seven step three officer na Bo de earn exactly wetin di structure talk, same as na Freetown. Retro-pay en ghost-worker audit tool dem de live ya too.",
        "Establishment control de compare approved post dem against filled post dem, ministry by ministry. Over-establishment hiring de flag before e turn payroll liability, en vacancy dem de visible for workforce planning.",
        "Before any payroll run commit, di budget check de verify say allocation still de na every budget code wey di run go use. If one code don pass, di run de block — en na only documented override with reason able proceed. Na di payroll page, di budget balances panel de show exactly usai every code stand.",
        "Finally, di open-gov transparency portal — public page, no login need — wey de publish aggregate payroll statistics for yu ministry: headcount, wage bill trend dem, en grade distribution. Citizen en journalist dem de see di number dem; personal data de stay protected.",
        "Structure, establishment, budget discipline, en daylight — di four pillar dem of clean government payroll. Go take di government modules quiz na di Training Center for complete yu certification.",
    ],
}
