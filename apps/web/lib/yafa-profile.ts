"use client";

export type ConfirmedYafaProfile = {
  has_profile: boolean;
  shade_id?: string;
  shade_name?: string;
  shade_code?: string;
  hex?: string;
};

export async function getConfirmedYafaProfile(): Promise<ConfirmedYafaProfile | null> {
  const response = await fetch("/api/v1/me/beauty-profile", { credentials: "include", cache: "no-store" });
  if (response.status === 401 || response.status === 404) return null;
  if (!response.ok) throw new Error("Unable to load your Yafa profile.");
  const profile = await response.json() as ConfirmedYafaProfile;
  return profile.has_profile ? profile : null;
}
