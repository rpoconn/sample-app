# Situation 1: New jurisdictions, summary of changes

## The changes

**1. Every new jurisdiction triggers a notification for users, if their company's license covers it**

- **What it says:** the new jurisdiction's name and where it sits, for example *San Jose (California, US)*.
- **The Add button:** **Add to my jurisdictions** turns on just that jurisdiction in the user's selections, in one click. They don't need to open the Jurisdictions screen or find it in the tree. Their other selections stay as they are, and they can turn it off later on the Jurisdictions screen like any other jurisdiction.
- **If they don't click Add:** nothing changes. Their saved settings mean what they always meant.
- **Mute:** users can turn new-jurisdiction notifications off completely. They can also limit them to certain areas using subscriptions, described next.

**2. A Subscriptions tab, to control what happens when jurisdictions are added in a location**

A subscription is a location (a country, state, or province) plus a few options:

| Option | Choices |
|---|---|
| **Action** | **Notify me** (a notification with the Add button) or **Auto-add** (turned on automatically, with a notification and Undo) |
| **Include** | ☑ New states / provinces ☑ New cities |
| **Cities** | ○ In every state ○ **Only in states I already have selected** |

- **Adding a subscription:**
    - On the **Subscriptions tab**, type a location name (*Unit…* → *United States*) and it's added to the list with default options, which can then be changed.
    - From the **⋯ menu** on any row of the Jurisdictions tree, choose **Notify me about new jurisdictions here** or **Auto-add new jurisdictions here**.
- **The "only in states I already have selected" option** follows the user's current choices: if they turn a state on later, its new cities start being covered too.
- **Limiting notifications to certain areas:** a user with any *Notify me* subscriptions hears only about jurisdictions those subscriptions cover. A user with none hears about every licensed new jurisdiction, unless muted.
- **Licensing still applies:** only jurisdictions the company's license covers are added automatically.

Example Subscriptions tab:

```
Subscriptions                          [ Add a location… ]

United States   Auto-add   States ✓  Cities ✓ (only in states I have selected)
Canada          Notify me  Provinces ✓  Cities ✓ (every province)
```

## How it works for each persona

**Jurisdiction holder** (responsible for a subset)

- Subscribes to their area, for example *California → Auto-add*. New jurisdictions there show up on their own.
- Because they have a subscription, notifications only cover their area, and nothing outside it reaches them.

**Jurisdiction manager** (manages a team, or works alone as a single operator)

- A team manager uses *Notify me* on their countries to see everything new and decide what to add.
- A single operator who wants everything uses *United States → Auto-add* and *Canada → Auto-add*, so "everything" now includes new jurisdictions.
- A single operator who deliberately left out some states uses *Cities: only in states I already have selected*. They get new states and new cities, but never cities in states they chose not to cover.

## The three cases

| Case | What happens |
|---|---|
| **All US states selected, Montana added** | **No subscription:** notification, and **Add** turns Montana on. **Subscribed to *United States*, new states included:** added automatically (*Auto-add*) or a notification (*Notify me*). |
| **California selected (Illinois not), San Jose added** | **No subscription:** notification, and **Add** turns San Jose on. **Subscribed to *United States* or *California*, new cities included:** covered, with either city option, because California is selected. Illinois doesn't matter. |
| **Alabama deselected, city added under Alabama** | **Subscribed to *United States* with *Cities: only in states I already have selected*:** not added and no notification, so the deselection is respected. **With *Cities: in every state*:** covered, because the user chose that, and Auto-add offers Undo. **No subscription:** notification only, and nothing changes. |

**Why "all states selected" isn't treated as a subscription:** selecting every state today says nothing about the future. A subscription is the user saying so explicitly, and its options say exactly how far it reaches.

## Why we didn't use the other approaches

| Approach | Why not |
|---|---|
| **A global auto opt-in switch, plus a rule about parents and siblings** (e.g. "all siblings selected means auto-add") | The rule is hidden and surprising. It breaks on grouping rows that can't be selected, and on countries without a "National" row. A subscription's options say the same thing explicitly. |
| **An auto opt-in checkbox on every jurisdiction** | Hundreds of checkboxes. A subscriptions list holds a few entries a user types in. |
| **Notifications sent only to users who seem related to the new jurisdiction** | The system would be guessing who wants what, and every guess risks surprising someone. Users choose what they hear through subscriptions instead. |
| **Admin-assigned owners for each branch of the tree** | Clear accountability, but it needs a new admin screen, a setup step, and handling for when owners leave, which is too much for this problem. It could build on subscriptions later, by letting a manager add subscriptions for their team. |
| **A flattened list where parents become tags, with subscriptions as saved tag filters** | Very flexible, but users would have to learn filter logic (AND/OR, exclusions), and the hierarchy people expect from geography would be lost. A location with a couple of options covers the real cases, including Alabama, with nothing new to learn. |
