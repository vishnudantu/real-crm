import test from "node:test";
import assert from "node:assert/strict";
import {
  channelDisplayName,
  filterMembersByName,
  groupMessagesByDay,
  unreadBadgeLabel,
} from "../../src/teamchat/teamchatModel.ts";
import type { TeamChannel, TeamMessage, TeamStaffUser } from "../../src/teamchat/teamchatModel.ts";

function message(id: string, createdAt: string, body = id): TeamMessage {
  return {
    id, channel_id: "channel-1", author_user_id: "user-1", author: null,
    body, mentions: [], created_at: createdAt, edited_at: null,
  };
}

const admin: TeamStaffUser = { id: "a", full_name: "Anita Admin", email: "anita@example.test", role: "ADMIN" };
const sales: TeamStaffUser = { id: "b", full_name: "Ravi Sales", email: "ravi@example.test", role: "SALES_EXECUTIVE" };

test("groupMessagesByDay sorts chronologically without mutating newest-first input", () => {
  const input = [
    message("c", "2026-11-23T02:00:00Z"),
    message("b", "2026-11-22T10:00:00Z"),
    message("a", "2026-11-22T09:00:00Z"),
  ];
  const original = input.map((item) => item.id);
  const groups = groupMessagesByDay(input);
  assert.deepEqual(groups.map((group) => group.day), ["2026-11-22", "2026-11-23"]);
  assert.deepEqual(groups[0].messages.map((item) => item.id), ["a", "b"]);
  assert.deepEqual(groups[1].messages.map((item) => item.id), ["c"]);
  assert.deepEqual(input.map((item) => item.id), original);
});

test("groupMessagesByDay handles empty streams and deterministic timestamp ties", () => {
  assert.deepEqual(groupMessagesByDay([]), []);
  const groups = groupMessagesByDay([
    message("b", "2026-11-22T09:00:00Z"),
    message("a", "2026-11-22T09:00:00Z"),
  ]);
  assert.deepEqual(groups[0].messages.map((item) => item.id), ["a", "b"]);
});

test("unreadBadgeLabel clamps badges and safely handles invalid counts", () => {
  assert.equal(unreadBadgeLabel(0), "0");
  assert.equal(unreadBadgeLabel(-1), "0");
  assert.equal(unreadBadgeLabel(1), "1");
  assert.equal(unreadBadgeLabel(99), "99");
  assert.equal(unreadBadgeLabel(100), "99+");
  assert.equal(unreadBadgeLabel(9999), "99+");
  assert.equal(unreadBadgeLabel(Number.NaN), "0");
});

test("filterMembersByName matches full names and emails case-insensitively", () => {
  assert.deepEqual(filterMembersByName([admin, sales], " anita "), [admin]);
  assert.deepEqual(filterMembersByName([admin, sales], "RAVI@EXAMPLE"), [sales]);
  assert.deepEqual(filterMembersByName([admin, sales], "nobody"), []);
  assert.deepEqual(filterMembersByName([admin, sales], " "), [admin, sales]);
});

test("channelDisplayName resolves direct recipients and preserves channel names", () => {
  const direct: TeamChannel = {
    id: "1", name: "dm-9f2c1a7b44e08d31a6b5c2f9017e34d8", topic: null, kind: "DIRECT", is_general: false,
    created_by: "a", created_at: "2026-11-22T00:00:00Z", unread_count: 0,
    member_count: 2,
    members: [
      { user_id: "a", role: "MEMBER", joined_at: "2026-11-22T00:00:00Z", last_read_at: null, user: admin },
      { user_id: "b", role: "MEMBER", joined_at: "2026-11-22T00:00:00Z", last_read_at: null, user: sales },
    ],
  };
  const channel = { ...direct, name: "leasing", kind: "CHANNEL" as const };
  // Names are opaque hashes now; the peer is resolved from the member list.
  assert.equal(channelDisplayName(direct, "a", [admin, sales]), "Ravi Sales");
  assert.equal(channelDisplayName(direct, "b", [admin, sales]), "Anita Admin");
  assert.equal(channelDisplayName(channel, "a", []), "leasing");
  // Without member data there is no name-based fallback: generic label only.
  const bare = { ...direct, members: [] };
  assert.equal(channelDisplayName(bare, "a", [admin, sales]), "Direct message");
});
