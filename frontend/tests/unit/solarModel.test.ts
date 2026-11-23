import test from "node:test";
import assert from "node:assert/strict";
import {
  bearingToCompass,
  classifyExposure,
  comfortTone,
  COMPASS_LABELS,
  dayForSeason,
  EXPOSURE_VISUALS,
  facingTextToBearing,
  formatMinutesAsTime,
  isFacadeInSun,
  facadeSunLabel,
  minutesToLocalTime,
  isoToLocal,
  localToMinutes,
  normalizeBearing,
  scoreUnitFacing,
  solarPosition,
  suggestUtcOffset,
  SEASONS,
} from "../../src/solar/solarModel.ts";
import type { SunPathDay } from "../../src/solar/solarModel.ts";

// ---------------------------------------------------------------------------
// Compass
// ---------------------------------------------------------------------------

test("normalizeBearing wraps negatives and >360", () => {
  assert.equal(normalizeBearing(0), 0);
  assert.equal(normalizeBearing(360), 0);
  assert.equal(normalizeBearing(450), 90);
  assert.equal(normalizeBearing(-90), 270);
  assert.equal(normalizeBearing(-360), 0);
  assert.ok(Math.abs(normalizeBearing(725.5) - 5.5) < 1e-9);
});

test("bearingToCompass snaps to nearest of 16 sectors", () => {
  assert.equal(bearingToCompass(0), "N");
  assert.equal(bearingToCompass(90), "E");
  assert.equal(bearingToCompass(180), "S");
  assert.equal(bearingToCompass(270), "W");
  assert.equal(bearingToCompass(45), "NE");
  assert.equal(bearingToCompass(22.5), "NNE");
  assert.equal(bearingToCompass(11.24), "N");
  assert.equal(bearingToCompass(11.26), "NNE");
  assert.equal(bearingToCompass(340), "NNW");
  // 348.75 is the exact NNW/N boundary; the backend rounds it to N.
  assert.equal(bearingToCompass(348.75), "N");
  assert.equal(bearingToCompass(359), "N");
  assert.equal(COMPASS_LABELS.length, 16);
});

test("facingTextToBearing parses text, numbers, and compass labels", () => {
  assert.equal(facingTextToBearing("East"), 90);
  assert.equal(facingTextToBearing("north"), 0);
  assert.equal(facingTextToBearing("North East"), 45);
  assert.equal(facingTextToBearing("South-West"), 225);
  assert.equal(facingTextToBearing("E"), 90);
  assert.equal(facingTextToBearing("NNW"), 337.5);
  assert.equal(facingTextToBearing("90"), 90);
  assert.equal(facingTextToBearing("450"), 90);
  assert.equal(facingTextToBearing(null), null);
  assert.equal(facingTextToBearing(""), null);
  assert.equal(facingTextToBearing("corner unit"), null);
});

// ---------------------------------------------------------------------------
// NOAA solar position (Hyderabad ≈ 17.385° N, 78.4867° E)
// ---------------------------------------------------------------------------

test("solarPosition at night returns negative elevation", () => {
  const pos = solarPosition(17.385, 78.4867, {
    year: 2026, month: 3, day: 20,
    hour: 0, minute: 0, second: 0,
    utcOffsetHours: 5.5,
  });
  assert.ok(pos.elevation < 0, `expected negative elevation, got ${pos.elevation}`);
});

test("solarPosition near local noon is high in the sky", () => {
  // Solar noon in Hyderabad in late March is ~12:20 IST.
  const pos = solarPosition(17.385, 78.4867, {
    year: 2026, month: 3, day: 20,
    hour: 12, minute: 20, second: 0,
    utcOffsetHours: 5.5,
  });
  // Equinox noon elevation ≈ 90 - |latitude| = ~72.6°.
  assert.ok(pos.elevation > 65 && pos.elevation < 80, `elevation ${pos.elevation}`);
});

test("solarPosition morning sun is in the eastern half (azimuth 0-180)", () => {
  const pos = solarPosition(17.385, 78.4867, {
    year: 2026, month: 6, day: 21,
    hour: 8, minute: 0, second: 0,
    utcOffsetHours: 5.5,
  });
  assert.ok(pos.elevation > 0);
  assert.ok(pos.azimuth > 0 && pos.azimuth < 180, `azimuth ${pos.azimuth}`);
});

test("solarPosition afternoon sun is in the western half (azimuth 180-360)", () => {
  const pos = solarPosition(17.385, 78.4867, {
    year: 2026, month: 6, day: 21,
    hour: 16, minute: 0, second: 0,
    utcOffsetHours: 5.5,
  });
  assert.ok(pos.elevation > 0);
  assert.ok(pos.azimuth > 180 && pos.azimuth < 360, `azimuth ${pos.azimuth}`);
});

test("solarPosition summer noon is higher than winter noon", () => {
  const base = { year: 2026, day: 21, hour: 12, minute: 20, second: 0, utcOffsetHours: 5.5 };
  const summer = solarPosition(17.385, 78.4867, { ...base, month: 6 });
  const winter = solarPosition(17.385, 78.4867, { ...base, month: 12 });
  assert.ok(summer.elevation > winter.elevation);
});

test("isoToLocal shifts UTC ISO string to site-local civil time", () => {
  const local = isoToLocal("2026-03-20T06:45:00+00:00", 5.5);
  assert.equal(local.hour, 12);
  assert.equal(local.minute, 15);
  assert.equal(local.year, 2026);
  assert.equal(local.month, 3);
  assert.equal(local.day, 20);
  assert.equal(local.utcOffsetHours, 5.5);
});

test("localToMinutes and minutesToLocalTime round-trip", () => {
  const local = isoToLocal("2026-06-21T00:30:00+00:00", 5.5);
  const minutes = localToMinutes(local);
  assert.equal(minutes, 360); // 6:00
  const rebuilt = minutesToLocalTime(minutes, local);
  assert.equal(rebuilt.hour, 6);
  assert.equal(rebuilt.minute, 0);
});

test("formatMinutesAsTime renders 12-hour clock", () => {
  assert.equal(formatMinutesAsTime(0), "12:00 AM");
  assert.equal(formatMinutesAsTime(360), "6:00 AM");
  assert.equal(formatMinutesAsTime(720), "12:00 PM");
  assert.equal(formatMinutesAsTime(780), "1:00 PM");
  assert.equal(formatMinutesAsTime(23 * 60 + 5), "11:05 PM");
  assert.equal(formatMinutesAsTime(-30), "11:30 PM");
});

// ---------------------------------------------------------------------------
// Scoring mirror
// ---------------------------------------------------------------------------

test("classifyExposure matches backend sector boundaries", () => {
  assert.equal(classifyExposure(0), "diffused");
  assert.equal(classifyExposure(44.9), "diffused");
  assert.equal(classifyExposure(45), "morning");
  assert.equal(classifyExposure(90), "morning");
  assert.equal(classifyExposure(134.9), "morning");
  assert.equal(classifyExposure(135), "bright");
  assert.equal(classifyExposure(180), "bright");
  assert.equal(classifyExposure(225), "afternoon");
  assert.equal(classifyExposure(270), "afternoon");
  assert.equal(classifyExposure(314.9), "afternoon");
  assert.equal(classifyExposure(315), "diffused");
});

test("scoreUnitFacing cardinal scores match backend", () => {
  assert.equal(scoreUnitFacing(90).comfort_score, 85); // East
  assert.equal(scoreUnitFacing(0).comfort_score, 75); // North
  assert.equal(scoreUnitFacing(180).comfort_score, 60); // South
  assert.equal(scoreUnitFacing(270).comfort_score, 40); // West
});

test("scoreUnitFacing applies +5 corner bonus and premium bump", () => {
  const ne = scoreUnitFacing(45);
  assert.equal(ne.facing_label, "NE");
  assert.equal(ne.exposure_class, "morning");
  assert.equal(ne.comfort_score, 90); // 85 + 5
  assert.equal(ne.pricing_premium_min_pct, 4); // 3 + 1
  assert.equal(ne.pricing_premium_max_pct, 9); // 7 + 2
  assert.ok(ne.vastu_note.includes("cross-ventilation"));
});

test("scoreUnitFacing afternoon premium is negative-to-zero", () => {
  const w = scoreUnitFacing(270);
  assert.equal(w.pricing_premium_min_pct, -2);
  assert.equal(w.pricing_premium_max_pct, 0);
  assert.ok(w.pricing_advisory.startsWith("Advisory premium: -2% to +0%"));
});

test("scoreUnitFacing normalizes out-of-range bearings", () => {
  const a = scoreUnitFacing(450);
  const b = scoreUnitFacing(90);
  assert.equal(a.comfort_score, b.comfort_score);
  assert.equal(a.facing_label, b.facing_label);
});

// ---------------------------------------------------------------------------
// Presentation helpers
// ---------------------------------------------------------------------------

test("comfortTone bands scores into tones", () => {
  assert.equal(comfortTone(90), "emerald");
  assert.equal(comfortTone(80), "emerald");
  assert.equal(comfortTone(75), "sky");
  assert.equal(comfortTone(60), "amber");
  assert.equal(comfortTone(40), "rose");
});

test("every exposure class has a visual with label and tone", () => {
  for (const key of ["morning", "afternoon", "diffused", "bright"] as const) {
    const visual = EXPOSURE_VISUALS[key];
    assert.ok(visual.label.length > 0);
    assert.ok(visual.description.length > 0);
    assert.ok(["emerald", "amber", "sky", "rose"].includes(visual.tone));
  }
});

// ---------------------------------------------------------------------------
// Facade sun geometry
// ---------------------------------------------------------------------------

test("isFacadeInSun returns false below the horizon", () => {
  assert.equal(isFacadeInSun(90, 90, -5), false);
  assert.equal(facadeSunLabel(false, -5), "Night — sun below horizon");
});

test("east facade is lit in the morning, shaded in the afternoon", () => {
  // East facade outward normal = 90°.
  assert.equal(isFacadeInSun(90, 90, 30), true); // sun due east
  assert.equal(isFacadeInSun(90, 60, 20), true); // ENE, within 90°
  assert.equal(isFacadeInSun(90, 270, 40), false); // sun due west
});

test("west facade is lit in the afternoon", () => {
  assert.equal(isFacadeInSun(270, 270, 35), true);
  assert.equal(isFacadeInSun(270, 90, 35), false);
});

test("facade exactly 90° off the sun is not in direct sun", () => {
  assert.equal(isFacadeInSun(0, 90, 45), false);
  assert.equal(isFacadeInSun(0, 270, 45), false);
});

test("facadeSunLabel describes direct sun vs shade above horizon", () => {
  assert.equal(facadeSunLabel(true, 30), "Direct sun on this facade");
  assert.equal(facadeSunLabel(false, 30), "Shade — sun behind this facade");
});

// ---------------------------------------------------------------------------
// Seasons
// ---------------------------------------------------------------------------

function day(date: string): SunPathDay {
  return {
    date,
    sunrise: `${date}T01:00:00+00:00`,
    sunset: `${date}T13:00:00+00:00`,
    solar_noon: `${date}T07:00:00+00:00`,
    day_length_hours: 12,
  };
}

test("dayForSeason matches each representative date", () => {
  const days = [day("2026-03-20"), day("2026-06-21"), day("2026-09-22"), day("2026-12-21")];
  assert.equal(dayForSeason(days, "summer")?.date, "2026-06-21");
  assert.equal(dayForSeason(days, "equinox")?.date, "2026-03-20");
  assert.equal(dayForSeason(days, "winter")?.date, "2026-12-21");
  assert.equal(SEASONS.length, 3);
});

test("dayForSeason falls back to autumnal equinox when vernal missing", () => {
  const days = [day("2026-09-22")];
  assert.equal(dayForSeason(days, "equinox")?.date, "2026-09-22");
  assert.equal(dayForSeason(days, "summer"), null);
  assert.equal(dayForSeason([], "summer"), null);
});

test("suggestUtcOffset snaps longitude to half-hour grid", () => {
  // Hyderabad longitude gives 5 by the 15°/hour rule; IST is actually 5.5, so
  // the studio overrides the offset explicitly for India rather than relying
  // on this generic suggestion.
  assert.equal(suggestUtcOffset(78.4867), 5);
  assert.equal(suggestUtcOffset(82.5), 5.5); // IST central meridian
  assert.equal(suggestUtcOffset(0), 0);
  assert.equal(suggestUtcOffset(-74), -5); // New York approx
});
