export {
  formatInr,
  formatShortDate,
  saleInputClasses,
  saleLabelClasses,
  salePrimaryButton,
  saleSecondaryButton,
} from "../admin/sales/salesBookingUi";

export function shortReference(value: string): string {
  return value.length > 8 ? `${value.slice(0, 8)}…` : value;
}
