/** Optional IDs preserve compatibility with legacy single-tenant profiles. */
export function profileMatchesTenant(
  profileTenantId: string | null | undefined,
  brandingTenantId: string | null,
): boolean {
  return !profileTenantId || !brandingTenantId || profileTenantId === brandingTenantId;
}
