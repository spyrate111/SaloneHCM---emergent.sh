export default function Settings() {
  return (
    <div className="space-y-6" data-testid="settings-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Settings</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Organization</h1>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Company</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[["Legal name", "Demo Salone Ltd."], ["TIN", "TIN-100200300"], ["NASSIT employer", "NS-EMP-001"], ["Country", "Sierra Leone"], ["Tier", "SaloneHCM Professional"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0"><dt className="text-[#525860]">{k}</dt><dd className="font-medium">{v}</dd></div>
            ))}
          </dl>
        </div>
        <div className="bg-white border border-[#E2DFD6] rounded-lg p-6">
          <h3 className="font-heading text-lg font-semibold">Pay configuration</h3>
          <dl className="mt-4 space-y-3 text-sm font-data">
            {[["Currency", "SLE (Sierra Leonean Leone)"], ["Pay frequency", "Monthly"], ["Pay day", "Last working day"], ["NRA filing day", "15th of next month"]].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-[#F1EEE6] pb-2 last:border-0"><dt className="text-[#525860]">{k}</dt><dd className="font-medium">{v}</dd></div>
            ))}
          </dl>
        </div>
      </div>
    </div>
  );
}
