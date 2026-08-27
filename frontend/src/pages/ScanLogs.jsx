import PayslipScanPanel from "../components/PayslipScanPanel";

export default function ScanLogs() {
  return (
    <div className="space-y-6" data-testid="scan-logs-page">
      <div>
        <div className="text-[11px] uppercase tracking-[0.18em] text-[#525860]">Anti-fraud</div>
        <h1 className="font-heading text-3xl sm:text-4xl font-bold mt-1">Payslip scan logs</h1>
        <p className="text-[#525860] text-sm mt-1">Every public QR verification scan across payslips — flagged rows indicate suspicious re-scanning.</p>
      </div>
      <PayslipScanPanel />
    </div>
  );
}
