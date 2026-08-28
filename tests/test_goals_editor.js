#!/usr/bin/env node
"use strict"

const fs = require("fs")
const path = require("path")
const vm = require("vm")

const src = fs
  .readFileSync(path.join(__dirname, "..", "Model.js"), "utf8")
  .replace(/^\s*\.pragma library\s*/m, "")

const context = {}
vm.createContext(context)
vm.runInContext(src, context)

const {
  applyGoalsCommand,
  emptyEditorState,
  cloneDraftGoals,
  goalsPayload,
  clampIndex,
  goalMatches,
  goalSourceOptions,
  matchIdentity,
  matchCovered,
  matchLabel,
  canonicalGoalMatch,
  goalList,
  barLabel,
  ICON_GOAL,
  ICON_WORDS,
} = context

let failed = 0
function assert(cond, msg) {
  if (!cond) {
    failed += 1
    console.error("FAIL", msg)
  }
}

function eq(a, b) {
  return JSON.stringify(a) === JSON.stringify(b)
}

const closed = emptyEditorState()

const opened = applyGoalsCommand(closed, "g", 2)
assert(opened.action === "open", "G opens from closed")
assert(opened.state.open === true, "open flag")
assert(opened.state.selected === 0, "first goal selected")
assert(opened.state.editing === -1, "nothing editable until a goal is chosen")
assert(opened.state.fieldFocused === false, "no field focus on open")

const typedG = applyGoalsCommand(
  { open: true, selected: 0, editing: 0, fieldFocused: true },
  "g",
  2
)
assert(typedG.action === "none", "typed G in a field does not finish")
assert(typedG.state.open === true, "editor stays open while typing G")

const doneWhileTyping = applyGoalsCommand(
  { open: true, selected: 0, editing: 0, fieldFocused: true },
  "done",
  2
)
assert(doneWhileTyping.action === "close", "G done finishes even with a field focused")
assert(doneWhileTyping.state.open === false, "done closes")
assert(doneWhileTyping.state.editing === -1, "done clears editing")
assert(doneWhileTyping.state.fieldFocused === false, "done clears field focus")

const gBrowse = applyGoalsCommand(
  { open: true, selected: 0, editing: -1, fieldFocused: false },
  "g",
  2
)
assert(gBrowse.action === "close", "G finishes from browse")
assert(gBrowse.state.open === false, "G browse closes")

const clicked = applyGoalsCommand(opened.state, "click", 2, 1)
assert(clicked.action === "edit", "clicking a goal edits that one")
assert(clicked.state.selected === 1 && clicked.state.editing === 1, "clicked goal is the editor")

const other = applyGoalsCommand(clicked.state, "click", 2, 0)
assert(other.state.editing === 0 && other.state.selected === 0, "click switches the edited goal")

const enter = applyGoalsCommand(opened.state, "edit", 2)
assert(enter.state.editing === 0, "enter edits the selected goal")

const down = applyGoalsCommand(clicked.state, "down", 2)
assert(down.action === "select", "down moves selection")
assert(down.state.selected === 1, "down clamps to last")
assert(down.state.editing === -1, "moving selection leaves edit mode")

const emptyOpen = applyGoalsCommand(closed, "open", 0)
assert(emptyOpen.state.selected === -1 && emptyOpen.state.editing === -1, "empty list has no selection")

const doneClosed = applyGoalsCommand(closed, "done", 0)
assert(doneClosed.action === "none", "done is a no-op when already closed")

const accepted = applyGoalsCommand(
  { open: true, selected: 1, editing: 1, fieldFocused: true },
  "accept",
  2
)
assert(accepted.action === "accept", "accept commits even with a field focused")
assert(accepted.state.open === true, "accept stays in the goals list")
assert(accepted.state.editing === -1, "accept leaves the form")
assert(accepted.state.fieldFocused === false, "accept blurs the field")
assert(accepted.state.selected === 1, "accept keeps the saved goal selected")

const enterInField = applyGoalsCommand(
  { open: true, selected: 0, editing: 0, fieldFocused: true },
  "enter",
  2
)
assert(enterInField.action === "accept", "Enter in a field saves and finishes")
assert(enterInField.state.editing === -1, "Enter leaves the form")
assert(enterInField.state.open === true, "Enter does not close the goals list")

const returnInField = applyGoalsCommand(
  { open: true, selected: 0, editing: 0, fieldFocused: true },
  "return",
  1
)
assert(returnInField.action === "accept", "Return is the same as Enter")

const acceptBrowse = applyGoalsCommand(
  { open: true, selected: 0, editing: -1, fieldFocused: false },
  "accept",
  2
)
assert(acceptBrowse.action === "none", "accept is a no-op until a goal is being edited")

assert(context.goalCanAccept({ matches: ["obsidian"] }) === true, "goal with a window can accept")
assert(context.goalCanAccept({ matches: [] }) === false, "new goal cannot accept until a window is picked")
assert(context.goalCanAccept(null) === false, "missing goal cannot accept")

assert(clampIndex(5, 3) === 2, "clamp high")
assert(clampIndex(-1, 3) === 0, "clamp low")
assert(clampIndex(1, 0) === -1, "clamp empty")

const drafts = cloneDraftGoals([
  { label: "Notes", target: 1000, match: "obsidian", net_words: 12, percent: 1 },
  { label: "X", target: 500, matches: ["site:x", "obsidian"], net_words: 40, percent: 8 },
])
assert(drafts.length === 2, "clone keeps both goals")
assert(eq(goalMatches(drafts[0]), ["obsidian"]), "clone expands match")
assert(eq(drafts[1].matches, ["site:x", "obsidian"]), "clone copies matches")
drafts[1].matches.push("nope")
const again = cloneDraftGoals([
  { label: "X", target: 500, matches: ["site:x", "obsidian"] },
])
assert(eq(again[0].matches, ["site:x", "obsidian"]), "clone does not alias matches")

const payload = goalsPayload([
  { label: "Notes", target: 1000, matches: ["obsidian"] },
  { label: "Dropped", target: 500, matches: [] },
  { label: "Write", target: 500, matches: ["obsidian", "site:x"] },
])
assert(payload.length === 2, "payload skips goals with no windows")
assert(payload[0].match === "obsidian" && payload[0].words === 1000, "single match stays a string")
assert(eq(payload[1].match, ["obsidian", "site:x"]), "several matches stay a list")

assert(matchIdentity("obsidian") === matchIdentity("class:md.obsidian.Obsidian"), "bare obsidian is the same window as the class")
assert(matchIdentity("activity:md.obsidian.Obsidian") === matchIdentity("class:md.obsidian.Obsidian"), "activity and class for Obsidian are the same window")
assert(matchIdentity("activity:grok · omarchy-wpm") === matchIdentity("herdr:omarchy-wpm"), "agent workspace is the herdr workspace")
assert(matchCovered(["obsidian"], "class:md.obsidian.Obsidian") === true, "picking Obsidian does not add a second match")
assert(matchLabel("class:md.obsidian.Obsidian") === "Obsidian", "class match is labeled Obsidian")
assert(matchLabel("class:chromium") === "Chromium", "browser class is Chromium, not Other")
assert(canonicalGoalMatch("md.obsidian.Obsidian", "md.obsidian.Obsidian") === "class:md.obsidian.Obsidian", "obsidian activity stores the class")
assert(canonicalGoalMatch("chromium · x", "chromium") === "site:x", "browser activity stores the site")
assert(canonicalGoalMatch("grok · omarchy-wpm", "foot") === "herdr:omarchy-wpm", "agent activity stores the workspace")

const picker = goalSourceOptions({
  active_site: "",
  active_herdr_workspace: "omarchy-wpm",
  active_activity: "grok · omarchy-wpm",
  active_class: "foot",
  activities: [
    { name: "grok · omarchy-wpm", app_class: "foot" },
    { name: "chromium · x", app_class: "chromium" },
    { name: "grok-bot", app_class: "grok-bot" },
    { name: "chromium", app_class: "chromium" },
    { name: "md.obsidian.Obsidian", app_class: "md.obsidian.Obsidian" },
    { name: "herdr · omarchy-wpm", app_class: "foot" },
    { name: "unknown", app_class: "unknown" },
  ],
  sites: [{ name: "x" }],
  herdr_workspaces: [{ name: "omarchy-wpm" }],
  apps: [
    { app_class: "foot" },
    { app_class: "chromium" },
    { app_class: "grok-bot" },
    { app_class: "md.obsidian.Obsidian" },
    { app_class: "unknown" },
  ],
})
const pickerLabels = picker.map(function (row) { return row.label })
assert(pickerLabels.filter(function (l) { return l === "Obsidian" }).length === 1, "Obsidian appears once")
assert(pickerLabels.filter(function (l) { return l === "omarchy-wpm" }).length === 1, "workspace appears once")
assert(pickerLabels.filter(function (l) { return l === "Grok Bot" }).length === 1, "Grok Bot appears once")
assert(pickerLabels.indexOf("Other") < 0, "picker does not say Other")
assert(pickerLabels.indexOf("Unknown") < 0, "picker skips unknown")
assert(pickerLabels.indexOf("Chromium") >= 0, "leftover browser is Chromium")
assert(picker[0].hint === "this window", "focused window is first")
assert(pickerLabels[pickerLabels.length - 1] === "Everything", "Everything is last")

const listed = goalList({
  goals: [{ label: "obsidian", match: "obsidian", matches: ["obsidian"], target: 1000, net_words: 8, percent: 1 }],
})
assert(listed.length === 1, "goalList keeps the obsidian goal")
assert(listed[0].target === 1000 && listed[0].net_words === 8, "goalList copies counts as numbers")

const chip = barLabel({
  state: "running",
  today_words: 1037,
  live_wpm: 0,
  goals: [{ label: "obsidian", match: "obsidian", target: 1000, net_words: 8 }],
})
assert(chip.indexOf(ICON_WORDS) === 0, "bar chip uses the document icon")
assert(chip.indexOf(ICON_GOAL) >= 0, "bar chip uses the target icon")
assert(chip.indexOf("1037") >= 0, "bar chip keeps today words")
assert(chip.indexOf("8/1000") >= 0, "bar chip shows the goal")

const liveChip = barLabel({
  state: "running",
  today_words: 1037,
  live_wpm: 42,
  goals: [{ label: "obsidian", match: "obsidian", target: 1000, net_words: 8 }],
})
assert(liveChip.indexOf("42") >= 0, "bar chip keeps live WPM")
assert(liveChip.indexOf("1037") >= 0, "bar chip still has today words while live")

if (failed) {
  console.error(failed + " failed")
  process.exit(1)
}
console.log("ok")
