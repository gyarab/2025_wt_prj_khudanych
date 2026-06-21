/**
 * cx = "class names". Spojí třídy mezerou a zahodí ty, co jsou
 * false / null / undefined. Hodí se na podmíněné třídy:
 *
 *   cx(styles.btn, isActive && styles.active)
 *   // isActive === true  → "btn active"
 *   // isActive === false → "btn"   (to false se vyhodí)
 *
 * Je to ruční minimalistická verze populární knihovny `clsx` — děláme si ji
 * sami, abys viděl, že na tom není nic kouzelného.
 */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
