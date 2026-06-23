const LABELS = {
  paid: "ชำระแล้ว",
  pending: "รอชำระ",
  expired: "หมดอายุ",
  canceled: "ยกเลิก",
  refunded: "คืนเงินแล้ว",
};

export default function StatusBadge({ status }) {
  return <span className={`badge ${status}`}>{LABELS[status] || status}</span>;
}
