# iKernel-Game Communication Sequence Diagram

**Based on:** Italian Development Guide v1.5 (OGAPI v2.20.0.0)

> **IMPORTANT NOTE:** The original Italian Development Guide v1.5 contains some internal inconsistencies:
> - Section numbers 5.5-5.10 have mismatched titles and content (e.g., section titled "CommitStake" describes RollbackStake)
> - EscrowWinnings is marked as "removed" in version history but still referenced in Recovery section
> - Recovery scenarios are simplified and may not show all required calls (e.g., SetCheckpoint)
>
> This document attempts to resolve these inconsistencies based on the actual content descriptions.

---

## Table of Contents

1. [Overview](#overview)
2. [Post-Initialization State](#post-initialization-state)
3. [Main Game Loop](#main-game-loop)
4. [Game Cycle - Basic Flow](#game-cycle---basic-flow)
5. [Game Cycle - With Risk](#game-cycle---with-risk)
6. [Game Cycle - With Features](#game-cycle---with-features)
7. [Event Handling](#event-handling)
8. [Tax Handling](#tax-handling)
9. [Player Limits](#player-limits)
10. [Recovery Flow](#recovery-flow)
11. [Shutdown Sequence](#shutdown-sequence)
12. [State Machine Summary](#state-machine-summary)

---

## Overview

```
+------------------+                      +------------------+
|      GAME        |  <-- OGAPI DLL -->   |     iKernel      |
+------------------+                      +------------------+
        |                                         |
        |  1. All calls are ASYNCHRONOUS          |
        |  2. Responses come via CALLBACKS        |
        |  3. Callbacks triggered ONLY during     |
        |     ProcessCallbacks() calls            |
        |  4. Data valid ONLY during callback     |
        |     lifetime (deep copy required)       |
        |                                         |
```

**Critical Rules:**
- All OGAPI interaction must be on the **main thread** (not thread-safe)
- Must call `adminInterface->processCallbacks()` ~every frame
- Must call `CabinetButtonsInterface->processCallbacks()` ~every frame
- Must send `heartbeat()` every **15 seconds** (timeout at 25s)
- Game must **block game flow** while waiting for responses (but continue rendering)

---

## Post-Initialization State

After successful initialization, the game is in **IDLE** state:

```
+------------------------------------------------------------------+
|                    POST-INITIALIZATION STATE                      |
+------------------------------------------------------------------+
                               |
                               v
        +----------------------------------------------+
        |  MANDATORY CALLBACKS (must register):        |
        |  - OnCreditChangedEvent                      |
        |  - OnExitDeferredEvent                       |
        |  - OnExitEvent                               |
        |  - OnLimitsEvent                             |
        |  - OnCashoutEndEvent                         |
        +----------------------------------------------+
        |  OPTIONAL CALLBACKS:                         |
        |  - OnTaxEvent (v2.20.0.0+, register         |
        |    separately if LegacyTaxPopup=FALSE)      |
        |  - ButtonCallback (via CabinetButtons)       |
        +----------------------------------------------+
                               |
                               v
        +----------------------------------------------+
        |  CONTINUOUS OPERATIONS (every frame):        |
        |  - adminInterface->processCallbacks()        |
        |  - CabinetButtonsInterface->processCallbacks()|
        +----------------------------------------------+
                               |
                               v
        +----------------------------------------------+
        |  PERIODIC OPERATIONS (every ~15 sec):        |
        |  - LegionItalyInterface->heartbeat()         |
        +----------------------------------------------+
                               |
                               v
                    [ WAITING FOR PLAYER INPUT ]
                               |
                    (Player presses START button)
                               |
                               v
                    [ BEGIN GAME CYCLE ]
```

---

## Main Game Loop

```
                         +------------------+
                         |   GAME RUNNING   |
                         +------------------+
                                  |
                                  v
            +---------------------------------------------+
            |            MAIN LOOP (every frame)          |
            +---------------------------------------------+
                                  |
         +------------------------+------------------------+
         |                        |                        |
         v                        v                        v
+------------------+   +--------------------+   +------------------+
| processCallbacks |   | processCallbacks   |   | Check heartbeat  |
| (adminInterface) |   | (CabinetButtons)   |   | timer (15 sec)   |
+------------------+   +--------------------+   +------------------+
         |                        |                        |
         |                        |                        |
         v                        v                        v
+------------------+   +--------------------+   +------------------+
| Handle callbacks |   | Handle button      |   | Send heartbeat() |
| - Credit change  |   | state changes      |   | if needed        |
| - Limits         |   | (0=up, 1=down)     |   +------------------+
| - Exit events    |   +--------------------+
| - Tax events     |
+------------------+
         |
         +------------------------+------------------------+
                                  |
                                  v
                    +---------------------------+
                    |  IN GAME CYCLE?           |
                    +---------------------------+
                          /            \
                        YES             NO
                         |               |
                         v               v
              +----------------+   +------------------+
              | Continue cycle |   | Wait for START   |
              | processing     |   | button press     |
              +----------------+   +------------------+
```

---

## Game Cycle - Basic Flow

> **NOTE on EscrowWinnings/SetEscrow:** Version 1.5 of the guide states these calls are
> "no longer used" and removed. However, the Recovery section still references SetEscrow.
> This document follows v1.5 and does NOT include EscrowWinnings in the game cycle flow.
> The platform may still use escrow internally for recovery purposes.

```
+==============================================================================+
|                          BASIC GAME CYCLE (No Win)                           |
+==============================================================================+

    [ IDLE STATE - Waiting for player ]
                    |
                    | (Player presses START)
                    v
    +---------------------------------------+
    | 1. AskContinue()                      |
    |    --> CallbackWithIntInfo            |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
    [int == 1]          [int == 0 or error]
    (Continue)           (Must exit)
           |                 |
           v                 v
           |          +-------------+
           |          | LOG & EXIT  |
           |          | (graceful)  |
           |          +-------------+
           |
           v
    +---------------------------------------+
    | 2. StartGameCycle(gameCycleId)        |
    |    gameCycleId: null (new) or         |
    |                 previous (recovery)   |
    |    --> CallbackWithStringInfo         |
    |        (returns game cycle ID)        |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]          [error]
           |                 |
           |                 v
           |          +-------------+
           |          | LOG & EXIT  |
           |          +-------------+
           |
           | (Save gameCycleId to memento)
           v
    +---------------------------------------+
    | 3. ReserveStake(amount)               |
    |    amount: stake in cents (min 50,    |
    |            max 1000 = 10 EUR)         |
    |    --> CallbackWithReservedStakeInfo  |
    |        (status + token)               |
    +---------------------------------------+
                    |
                    | (OnCreditChangedEvent fired)
                    | (Update credit display)
                    |
           +--------+--------+
           |                 |
    [status=OK]        [status=NOT_AUTH]
    (save token)        or error
           |                 |
           v                 v
           |          +-------------+
           |          | LOG & EXIT  |
           |          +-------------+
           |
           | (Start "fake" animation - reels spinning)
           v
    +---------------------------------------+
    | 4. GetRandomInt32(lower, upper)       |
    |    OR GetRandomInts32(...) for multi  |
    |    - Bounds are INCLUSIVE             |
    |    - Range: -2^31 to 2^31-1           |
    |    - GetRandomInts32: max 32 numbers  |
    |    - Max total randomness: 2^1024     |
    |    --> CallbackWithIntInfo            |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]          [error]
           |                 |
           |                 v
           |    +----------------------------------+
           |    | Display error message 5 sec:    |
           |    | "Il terminale ha fallito la     |
           |    |  connessione al server RNG.     |
           |    |  La partita verra terminata"    |
           |    | DO NOT END GAME CYCLE           |
           |    | EXIT (for recovery)             |
           |    +----------------------------------+
           |
           | (Save random numbers to memento)
           | (Calculate game outcome)
           v
    +---------------------------------------+
    | 5. SetCheckpoint(phaseSummary,        |
    |                  phaseInfo)           |
    |    phaseInfo: {                       |
    |      phase: GAME_PHASE_PRIMARY,       |
    |      prize: 0 (no win),               |
    |      randomNumbers: [...],            |
    |      randomCount: n,                  |
    |      stake: amount                    |
    |    }                                  |
    |    --> CallbackWithNoData             |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 6. CommitStake(token)                 |
    |    token: from ReserveStake response  |
    |    --> CallbackWithNoData             |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]          [error]
           |                 |
           v                 v
           |          +-------------+
           |          | LOG & EXIT  |
           |          | (no message)|
           |          +-------------+
           |
           | (Display outcome animation)
           v
    +---------------------------------------+
    | 7. EndGameCycle(summary, null)        |
    |    summary: "R1:...|R2:...|Total:0"   |
    |    phaseInfo: null (already sent via  |
    |               SetCheckpoint)          |
    |    --> CallbackWithNoData             |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]          [error]
           |                 |
           v                 v
           |          +-------------+
           |          | LOG & EXIT  |
           |          +-------------+
           |
           | (Clear memento file)
           v
    +---------------------------------------+
    | 8. AskContinue()                      |
    |    --> CallbackWithIntInfo            |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
    [int == 1]          [int == 0]
           |                 |
           v                 v
    [ IDLE STATE ]    +-------------+
    (ready for         | LOG & EXIT  |
     next cycle)       +-------------+


+==============================================================================+
|                          BASIC GAME CYCLE (With Win)                         |
+==============================================================================+

    ... (same as above through SetCheckpoint with prize > 0) ...
                    |
                    v
    +---------------------------------------+
    | 6. CommitStake(token)                 |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 7. AwardWinnings(amount)              |   <-- ONLY IF prize > 0
    |    amount: total win in cents         |
    |    --> CallbackWithNoData             |
    |                                       |
    |    CRITICAL: Call ONLY ONCE per cycle |
    |    CRITICAL: Call close to EndGame    |
    +---------------------------------------+
                    |
           +--------+--------+
           |                 |
      [success]          [error]
           |                 |
           v                 v
           |          +-------------------+
           |          | LOG & EXIT        |
           |          | (no end cycle)    |
           |          | (no message)      |
           |          +-------------------+
           |
           | (Display win animation)
           | (OnCreditChangedEvent fired)
           | (Possibly OnTaxEvent if win > threshold)
           v
    +---------------------------------------+
    | 8. EndGameCycle(summary, null)        |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | 9. AskContinue()                      |
    +---------------------------------------+
                    |
                    v
              [ IDLE STATE ]
```

---

## Game Cycle - With Risk

```
+==============================================================================+
|                        GAME CYCLE WITH RISK (GAMBLE)                         |
+==============================================================================+

    ... (after CommitStake, player has winnings > 0) ...
                    |
                    v
        +----------------------------------+
        | Player chooses: RISK or COLLECT? |
        +----------------------------------+
                    |
         +----------+----------+
         |                     |
    [COLLECT]              [RISK]
         |                     |
         v                     v
    (skip to              +----------------------------------+
    AwardWinnings)        | RISK ENTRY                       |
                          | - Collect button must work here  |
                          | - Player can exit without risking|
                          +----------------------------------+
                                       |
                    +------------------+------------------+
                    |                                     |
            [Player collects]                    [Player takes risk]
                    |                                     |
                    v                                     v
            +----------------+              +----------------------------+
            | SetCheckpoint  |              | Start risk animation       |
            | phase: GAMBLE  |              +----------------------------+
            | prize: 0       |                            |
            | stake: 0       |                            v
            | (entered but   |              +----------------------------+
            |  didn't play)  |              | GetRandomInt32(lower,upper)|
            +----------------+              | --> CallbackWithIntInfo    |
                    |                       +----------------------------+
                    |                                     |
                    |                        (Save to memento)
                    |                        (Calculate risk outcome)
                    |                                     |
                    |                                     v
                    |                       +----------------------------+
                    |                       | SetCheckpoint              |
                    |                       | phase: GAME_PHASE_GAMBLE   |
                    |                       | prize: win amount (or 0)   |
                    |                       | randomNumbers: [riskRng]   |
                    |                       | stake: risked amount       |
                    |                       +----------------------------+
                    |                                     |
                    |                        +------------+------------+
                    |                        |                         |
                    |                   [WIN]                      [LOSE]
                    |                        |                         |
                    |                        v                         v
                    |            +------------------+      +------------------+
                    |            | Update winnings  |      | winnings = 0     |
                    |            | (e.g., x2, x4)   |      +------------------+
                    |            +------------------+                |
                    |                        |                       |
                    |         +--------------+--------------+        |
                    |         |                             |        |
                    |    [RISK AGAIN?]               [COLLECT]       |
                    |         |                             |        |
                    |         v                             |        |
                    |    (loop back to                      |        |
                    |     "Player takes risk")              |        |
                    |                                       |        |
                    +---------------+-----------------------+--------+
                                    |
                                    v
                    +-------------------------------+
                    | winnings > 0?                 |
                    +-------------------------------+
                              /          \
                            YES           NO
                             |             |
                             v             v
              +-------------------+   (skip AwardWinnings)
              | AwardWinnings     |         |
              | (total winnings)  |         |
              +-------------------+         |
                             |              |
                             +------+-------+
                                    |
                                    v
                    +-------------------------------+
                    | EndGameCycle(summary, null)   |
                    | summary includes risk details:|
                    | "...|[G:25,X2:W:50]"          |
                    +-------------------------------+
                                    |
                                    v
                            [ AskContinue ]
                                    |
                                    v
                            [ IDLE STATE ]
```

---

## Game Cycle - With Features

```
+==============================================================================+
|                    GAME CYCLE WITH FEATURES (Free/Extra Spins)               |
+==============================================================================+

    ... (after GetRandomInt32 returns feature trigger) ...
                    |
                    v
    +---------------------------------------+
    | SetCheckpoint (PRIMARY phase)         |
    | phase: GAME_PHASE_PRIMARY             |
    | prize: 0 (feature won, no cash)       |
    | randomNumbers: [baseRng]              |
    | stake: initial stake                  |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | CommitStake(token)                    |
    +---------------------------------------+
                    |
                    v
          +------------------+
          | FEATURE LOOP     |
          | (Free/Extra Spin)|
          +------------------+
                    |
                    v
    +==========================================+
    |           FOR EACH FEATURE SPIN          |
    +==========================================+
                    |
                    v
    +---------------------------------------+
    | GetRandomInt32(lower, upper)          |
    | --> CallbackWithIntInfo               |
    +---------------------------------------+
                    |
                    | (Save to memento)
                    | (Calculate spin outcome)
                    v
    +---------------------------------------+
    | SetCheckpoint                         |
    | phase: GAME_PHASE_FEATURE             |
    | prize: spin win (can be 0)            |
    | randomNumbers: [spinRng]              |
    | stake: 0 (free spin)                  |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | More spins remaining?                 |
    | (including retriggered spins)         |
    +---------------------------------------+
              /            \
            YES             NO
             |               |
             v               |
    (loop back to            |
     GetRandomInt32)         |
                             |
                             v
    +---------------------------------------+
    | All features complete                 |
    | Total winnings calculated             |
    +---------------------------------------+
                    |
                    v
         +--------------------+
         | winnings > 0?      |
         +--------------------+
               /        \
             YES         NO
              |           |
              v           |
    +------------------+  |
    | RISK OFFERED?    |  |
    +------------------+  |
          /      \        |
        YES      NO       |
         |        |       |
         v        |       |
    (see Risk     |       |
     flow above)  |       |
                  |       |
         +--------+-------+
         |
         v
    +-------------------------------+
    | winnings > 0?                 |
    +-------------------------------+
              /          \
            YES           NO
             |             |
             v             v
    +-------------------+  (skip)
    | AwardWinnings     |    |
    +-------------------+    |
             |               |
             +-------+-------+
                     |
                     v
    +---------------------------------------+
    | EndGameCycle(summary, null)           |
    | summary: "...|ES:5|FS:10|Total:250"   |
    +---------------------------------------+
                     |
                     v
             [ AskContinue ]
                     |
                     v
             [ IDLE STATE ]


+==============================================================================+
|                      ANCILLARY PHASE (In-Game Betting)                       |
+==============================================================================+

    Example: Blackjack Split/Double-Down, Bingo Extra Ball

                    |
                    v
    +---------------------------------------+
    | ReserveAdditionalStake(amount)        |
    | --> CallbackWithReservedStakeInfo     |
    | (can be called multiple times)        |
    +---------------------------------------+
                    |
                    | (OnCreditChangedEvent fired)
                    v
    +---------------------------------------+
    | GetRandomInt32 (for ancillary phase)  |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | SetCheckpoint                         |
    | phase: GAME_PHASE_ANCILLARY           |
    | prize: phase prize                    |
    | stake: additional stake amount        |
    +---------------------------------------+
                    |
                    v
    +---------------------------------------+
    | CommitStake(ancillary token)          |
    +---------------------------------------+
                    |
                    v
              (continue cycle...)
```

---

## Event Handling

```
+==============================================================================+
|                              EVENT HANDLING                                  |
|           (Events can arrive at ANY point via processCallbacks)              |
+==============================================================================+


+--------------------------------+
| OnCreditChangedEvent           |
+--------------------------------+
         |
         v
+--------------------------------+
| GetCredit()                    |
| --> CallbackWithCreditInfo     |
| Use: stakeableCredit field     |
| (value in cents)               |
+--------------------------------+
         |
         v
+--------------------------------+
| Update credit meter display    |
| immediately                    |
+--------------------------------+


+--------------------------------+
| OnExitDeferredEvent            |
+--------------------------------+
         |
         v
+--------------------------------+
| In game cycle?                 |
+--------------------------------+
       /          \
     YES           NO
      |             |
      v             v
+------------+  +------------+
| Set flag:  |  | Exit       |
| exitAfter  |  | immediately|
| CycleEnd   |  +------------+
+------------+
      |
      v
(Continue cycle,
 exit after
 EndGameCycle +
 AskContinue)


+--------------------------------+
| OnExitEvent                    |
+--------------------------------+
         |
         v
+--------------------------------+
| CRITICAL FAILURE               |
| Log and EXIT IMMEDIATELY       |
| regardless of state            |
+--------------------------------+


+--------------------------------+
| OnLimitsEvent                  |
| --> CallbackWithLimitsInfo     |
| {spendLimit, spendLimitRemain, |
|  timeLimit, timeLimitRemain}   |
+--------------------------------+
         |
         v
+----------------------------------+
| Limit breached?                  |
| (Limit > 0 && Remaining == 0)    |
+----------------------------------+
        /            \
      YES             NO
       |               |
       v               v
+----------------+  (continue
| Show dialog:   |   normally)
| Continue or    |
| Stop & Cashout?|
+----------------+
    /         \
CONTINUE    STOP
   |          |
   v          v
+--------+  +------------------------+
|SetLimits|  | If stake reserved:    |
|(0, 0)  |  |   RollbackStake()     |
+--------+  | Cashout()              |
   |        | Log reason             |
   v        | Wait for callback      |
(continue)  | Exit gracefully        |
            +------------------------+


+--------------------------------+
| OnCashoutEndEvent              |
+--------------------------------+
         |
         v
+--------------------------------+
| Cashout process completed      |
| (ticket printed or error)      |
+--------------------------------+


+--------------------------------+
| OnTaxEvent (v2.20.0.0+)        |
| --> CallbackWithStringInfo     |
| (XML with tax details)         |
+--------------------------------+
         |
         v
+--------------------------------+
| LegacyTaxPopup property?       |
+--------------------------------+
      /            \
   TRUE            FALSE
    |                |
    v                v
(ignore -         +------------------------+
 platform         | Parse XML:             |
 shows popup)     | minThresh, maxThresh,  |
                  | pct, fullAmount,       |
                  | taxableAmount,         |
                  | taxAmount              |
                  +------------------------+
                           |
                           v
                  +------------------------+
                  | Display tax popup      |
                  | (after win animation,  |
                  |  before credit update) |
                  | Player must acknowledge|
                  | Continue heartbeat +   |
                  | processCallbacks       |
                  +------------------------+
```

---

## Tax Handling

```
+==============================================================================+
|                              TAX FLOW DETAIL                                 |
+==============================================================================+

    ... (AwardWinnings called with amount > tax threshold) ...
                    |
                    v
    +---------------------------------------+
    | OnTaxEvent received (if v2+)          |
    | XML payload:                          |
    | <winTax>                              |
    |   <tax minThresh="20000"              |
    |        maxThresh="500000"             |
    |        pct="20"                       |
    |        fullAmount="32000"             |
    |        taxableAmount="12000"          |
    |        taxAmount="2400"/>             |
    | </winTax>                             |
    +---------------------------------------+
                    |
    +---------------------------------------+
    | Check: LegacyTaxPopup property        |
    +---------------------------------------+
              /            \
           TRUE            FALSE
            |                |
            v                v
    +----------------+  +----------------------------------+
    | Ignore event   |  | Calculate net win:               |
    | Platform shows |  | netWin = fullAmount - taxAmount  |
    | popup on exit  |  +----------------------------------+
    +----------------+               |
            |                        v
            |          +----------------------------------+
            |          | Reduce displayed credit by       |
            |          | netWin (so credit insertion      |
            |          | during popup shows correctly)    |
            |          +----------------------------------+
            |                        |
            |                        v
            |          +----------------------------------+
            |          | Display tax popup with:          |
            |          | - Gross win: fullAmount          |
            |          | - Tax threshold: minThresh       |
            |          | - Tax rate: pct%                 |
            |          | - Taxable amount: taxableAmount  |
            |          | - Tax deducted: taxAmount        |
            |          | - Net win: (calculated)          |
            |          +----------------------------------+
            |                        |
            |                        v
            |          +----------------------------------+
            |          | WAIT for player acknowledgment   |
            |          | - Disable hardware buttons       |
            |          | - START must NOT dismiss         |
            |          | - Continue heartbeat             |
            |          | - Continue processCallbacks      |
            |          +----------------------------------+
            |                        |
            |                        v
            |          +----------------------------------+
            |          | Player acknowledges              |
            |          | Dismiss popup                    |
            |          | OnCreditChangedEvent will have   |
            |          | net win value                    |
            |          +----------------------------------+
            |                        |
            +------------+-----------+
                         |
                         v
              [ Continue to EndGameCycle ]
```

---

## Player Limits

```
+==============================================================================+
|                           PLAYER LIMITS FLOW                                 |
+==============================================================================+


    +-----------------------------------------+
    | Player opens "Set Limits" interface     |
    | (via Imposta Limiti / Set Limit button) |
    +-----------------------------------------+
                      |
                      v
    +-----------------------------------------+
    | Player sets:                            |
    | - spendLimit (credit to play, cents)    |
    | - timeLimit (minutes)                   |
    | Either or both can be set               |
    +-----------------------------------------+
                      |
           +----------+-----------+
           |                      |
       [OK pressed]        [Annulla pressed]
           |                      |
           v                      v
    +----------------+    +------------------+
    | SetLimits      |    | SetLimits(0, 0)  |
    | (spend, time)  |    | (clear limits)   |
    +----------------+    +------------------+
           |                      |
           +-----------+----------+
                       |
                       v
              [ Continue game ]
                       |
                       v
    +==========================================+
    |     DURING GAMEPLAY - LIMIT MONITORING   |
    +==========================================+
                       |
                       v
    +-----------------------------------------+
    | OnLimitsEvent received                  |
    | LimitsInfo: {                           |
    |   spendLimit: X,      (0 = not set)     |
    |   spendLimitRemaining: Y,               |
    |   timeLimit: X,       (0 = not set)     |
    |   timeLimitRemaining: Y                 |
    | }                                       |
    | (Remaining = INT_MAX if not set)        |
    +-----------------------------------------+
                       |
                       v
    +-----------------------------------------+
    | Check: (Limit > 0) && (Remaining == 0)  |
    +-----------------------------------------+
               /              \
         BREACHED          NOT BREACHED
              |                  |
              v                  v
    +------------------+    (continue
    | In game cycle?   |     normally)
    +------------------+
          /        \
        YES        NO
         |          |
         v          v
    +---------+  +------------------+
    | Wait    |  | Show dialog      |
    | until   |  | immediately      |
    | cycle   |  +------------------+
    | ends    |          |
    +---------+          |
         |               |
         v               |
    +------------------+ |
    | After            | |
    | EndGameCycle +   | |
    | AskContinue      | |
    +------------------+ |
              |          |
              +----+-----+
                   |
                   v
    +-----------------------------------------+
    | Show "Limit Breached" dialog            |
    | Options: [Continue] [Stop & Cash Out]   |
    +-----------------------------------------+
                   |
        +----------+----------+
        |                     |
    [CONTINUE]           [STOP & CASH OUT]
        |                     |
        v                     v
    +-------------+   +--------------------------------+
    | SetLimits   |   | If stake reserved:             |
    | (0, 0)      |   |   RollbackStake(token)         |
    | (clear      |   +--------------------------------+
    |  limits)    |               |
    +-------------+               v
        |             +--------------------------------+
        v             | Cashout()                      |
    (player can       | --> CallbackWithNoData         |
     set new          +--------------------------------+
     limits and                   |
     continue)        +-----------+-----------+
                      |                       |
                 [success]               [error]
                      |                       |
                      v                       v
              +---------------+    +-----------------------------+
              | Wait for      |    | Show message 5 sec:         |
              | OnExitDeferred|    | "Unable to print ticket     |
              | or OnExit     |    |  for €X.XX" (include amount)|
              +---------------+    | Then exit to menu           |
                      |            +-----------------------------+
                      v
              [ Exit gracefully ]


    +==========================================+
    |        SPEND LIMIT - SPECIAL CASE        |
    |     (Check BEFORE CommitStake)           |
    +==========================================+

    +-----------------------------------------+
    | After ReserveStake(), wait for BOTH:    |
    | 1. ReserveStake callback                |
    | 2. OnLimitsEvent callback               |
    +-----------------------------------------+
                      |
                      v
    +-----------------------------------------+
    | Spend limit breached by this stake?     |
    +-----------------------------------------+
               /              \
             YES               NO
              |                 |
              v                 v
    +-------------------+   (continue with
    | Show limit dialog |    CommitStake)
    | BEFORE CommitStake|
    +-------------------+
              |
              v
    +-------------------+
    | If Stop & Cashout:|
    | RollbackStake()   |
    | then Cashout()    |
    +-------------------+
```

---

## Recovery Flow

```
+==============================================================================+
|                              RECOVERY FLOW                                   |
+==============================================================================+

    +------------------------------------------+
    | GAME START                               |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | After GetWriteableDirectory callback     |
    | Check: game.memento file exists?         |
    +------------------------------------------+
               /              \
          EXISTS          NOT EXISTS
             |                  |
             v                  v
    +------------------+   +-----------------+
    | Parse memento    |   | Normal startup  |
    | Check: unfinished|   | (no recovery)   |
    | game cycle?      |   +-----------------+
    +------------------+
          /        \
        YES        NO / INVALID
         |              |
         v              v
    +-----------+   +-----------------+
    | RECOVERY  |   | Normal startup  |
    | MODE      |   | (delete corrupt |
    +-----------+   |  memento)       |
         |          +-----------------+
         v
    +------------------------------------------+
    | Load from memento:                       |
    | - gameCycleId                            |
    | - current state/phase                    |
    | - saved random numbers                   |
    | - other game state                       |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | AskContinue()                            |
    | --> CallbackWithIntInfo                  |
    +------------------------------------------+
                      |
           +----------+----------+
           |                     |
      [int == 1]            [int == 0]
           |                     |
           v                     v
           |              +-------------+
           |              | LOG & EXIT  |
           |              +-------------+
           |
           v
    +------------------------------------------+
    | StartGameCycle(SAVED_GAMECYCLEID)        |
    | --> CallbackWithStringInfo               |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | Continue from saved state                |
    | (see recovery scenarios below)           |
    +------------------------------------------+


+==============================================================================+
|                         RECOVERY SCENARIOS                                   |
+==============================================================================+

SCENARIO 1: Terminated after StartGameCycle (before ReserveStake)
==================================================================

    Original flow:
    StartGameCycle --> [CRASH]

    Recovery flow:
    StartGameCycle(PREV_GCID)
         |
         v
    ReserveStake(amount)      <-- start fresh
         |
         v
    GetRandomInt32(...)
         |
         v
    SetCheckpoint(...)
         |
         v
    CommitStake(token)
         |
         v
    [AwardWinnings if win]
         |
         v
    EndGameCycle(...)


SCENARIO 2: Terminated after ReserveStake (before GetRandomInt32)
==================================================================

    Original flow:
    StartGameCycle
    ReserveStake --> [CRASH]

    Recovery flow (per original document):
    StartGameCycle(PREV_GCID)
         |
         v
    GetRandomInt32(...)       <-- Per original doc: no ReserveStake shown
         |
         v
    CommitStake(token)        <-- UNCLEAR: how to get token without ReserveStake?
         |
         v
    [AwardWinnings if win]
         |
         v
    EndGameCycle(...)

    WARNING: The original document's scenario is inconsistent!
    Text states: "interrupting credit handling invalidates both
    ReserveStake and CommitStake, requiring that both be called anew"

    RECOMMENDED SAFE APPROACH:
    StartGameCycle(PREV_GCID)
         |
         v
    ReserveStake(amount)      <-- Re-reserve to get new token
         |
         v
    GetRandomInt32(...)
         |
         v
    SetCheckpoint(...)
         |
         v
    CommitStake(NEW token)
         |
         v
    [AwardWinnings if win]
         |
         v
    EndGameCycle(...)


SCENARIO 3: Terminated after GetRandomInt32 (before CommitStake)
=================================================================

    Original flow:
    StartGameCycle
    ReserveStake
    GetRandomInt32 --> [CRASH]

    Recovery flow:
    StartGameCycle(PREV_GCID)
         |
         v
    ReserveStake(amount)      <-- must re-reserve (was rolled back)
         |
         v
    (use saved random numbers from memento)
         |
         v
    SetCheckpoint(...)
         |
         v
    CommitStake(token)        <-- use NEW token from re-reserve
         |
         v
    [AwardWinnings if win]
         |
         v
    EndGameCycle(...)


SCENARIO 4: Terminated after CommitStake (before AwardWinnings)
================================================================

    Original flow:
    StartGameCycle
    ReserveStake
    GetRandomInt32
    SetCheckpoint
    CommitStake --> [CRASH]

    Recovery flow:
    StartGameCycle(PREV_GCID)
         |
         v
    (stake already committed - don't re-reserve)
         |
         v
    [AwardWinnings if win]    <-- continue from here
         |
         v
    EndGameCycle(...)


SCENARIO 5: Terminated after AwardWinnings (before EndGameCycle)
=================================================================

    Original flow:
    StartGameCycle
    ReserveStake
    GetRandomInt32
    SetCheckpoint
    CommitStake
    AwardWinnings --> [CRASH]

    Recovery flow:
    StartGameCycle(PREV_GCID)
         |
         v
    EndGameCycle(...)         <-- only this remains


+==============================================================================+
|                    RECOVERY - CRITICAL NOTES                                 |
+==============================================================================+

    1. SetCheckpoint: DO NOT DUPLICATE
       - If a phase was already checkpointed, don't checkpoint again
       - Duplicates will be detected and flagged as errors
       - Recovery scenarios above don't show SetCheckpoint for brevity
       - In practice: call SetCheckpoint for phases NOT yet checkpointed

    2. Random Numbers:
       - Save ALL received random numbers to memento
       - On recovery, use saved numbers (don't request again)
       - Only request additional randomness if needed for remaining phases

    3. Memento File:
       - Must be named "game.memento" in working directory
       - Must be obfuscated (NOT human-readable)
       - Must have tamper protection (prevent editing)
       - MUST use safe file writing methodology:
         * Write to temporary file first
         * Then rename/move to game.memento
         * This prevents corruption on power loss during write

    4. Clear Memento:
       - Clear/reset after EndGameCycle succeeds
       - Do NOT retain completed cycles (no replay support)

    5. Recovery Attempts:
       - Platform allows LIMITED recovery attempts
       - After max attempts: terminal SUSPENDED
       - Platform awards last escrowed value (SetEscrow - deprecated but still used internally)
       - Platform clears memento to prevent infinite loops

    6. Credit Handling on Crash:
       - ReserveStake is automatically rolled back on crash (credit returned)
       - Text states: "interrupting credit handling invalidates both
         ReserveStake and CommitStake, requiring that both be called anew"
       - Safe approach: always re-call ReserveStake after crash if not yet committed
```

---

## Shutdown Sequence

```
+==============================================================================+
|                           SHUTDOWN SEQUENCE                                  |
+==============================================================================+


    +------------------------------------------+
    | EXIT TRIGGER                             |
    | - Player pressed Menu button             |
    | - OnExitEvent received                   |
    | - OnExitDeferredEvent + cycle complete   |
    | - Fatal error                            |
    | - Player cashed out                      |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | In game cycle?                           |
    +------------------------------------------+
           /                    \
         YES                     NO
          |                       |
          v                       |
    +-------------------+         |
    | Is it OnExit?     |         |
    +-------------------+         |
       /          \               |
     YES           NO             |
      |             |             |
      v             v             |
    (exit        +----------+     |
    immediately)| Complete  |     |
      |         | cycle     |     |
      |         | first     |     |
      |         +----------+     |
      |             |             |
      +------+------+-------------+
             |
             v
    +------------------------------------------+
    | 1. LegionItalyInterface->Exiting()       |
    |    --> CallbackWithNoData                |
    |    (iKernel allows 5000ms to complete)   |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | 2. Unload assets                         |
    |    - Graphics                            |
    |    - Sounds                              |
    |    - Other resources                     |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | 3. Continue calling processCallbacks()   |
    |    until shutdown is called              |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | 4. CabinetButtonsInterface->shutdown()   |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | 5. adminInterface->shutdown()            |
    |    (NO MORE CALLS AFTER THIS)            |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | 6. Terminate process                     |
    +------------------------------------------+


    +==========================================+
    |              CASHOUT FLOW                |
    +==========================================+

    +------------------------------------------+
    | Player presses Ticket Out button         |
    | (hardware or software)                   |
    +------------------------------------------+
                      |
                      v
    +------------------------------------------+
    | In game cycle?                           |
    +------------------------------------------+
           /                    \
         YES                     NO
          |                       |
          v                       v
    +-------------------+   +-------------------+
    | In Risk collect   |   | Cashout()         |
    | state?            |   | --> Callback      |
    +-------------------+   +-------------------+
       /          \               |
     YES           NO             |
      |             |             |
      v             v             |
    +----------+  (ignore         |
    | Collect  |   button)        |
    | winnings |                  |
    | & end    |                  |
    | cycle    |                  |
    +----------+                  |
          |                       |
          +----------+------------+
                     |
                     v
    +------------------------------------------+
    | Wait for Cashout callback                |
    +------------------------------------------+
           /                    \
      [success]              [error]
          |                       |
          v                       v
    +-------------------+   +-----------------------------+
    | Wait for          |   | Show message 5 sec:         |
    | OnExitDeferred    |   | "Unable to print ticket     |
    | or OnExit         |   |  for €X.XX" (show amount!)  |
    +-------------------+   +-----------------------------+
          |                       |
          |                       v
          |               +-------------------+
          |               | If OnExitDeferred |
          |               | during message:   |
          |               | Wait for 5 sec    |
          |               +-------------------+
          |                       |
          |                       v
          |               +-------------------+
          |               | If OnExit during  |
          |               | message: EXIT NOW |
          |               +-------------------+
          |                       |
          +----------+------------+
                     |
                     v
             [ Exit gracefully ]
```

---

## State Machine Summary

```
+==============================================================================+
|                      COMPLETE STATE MACHINE OVERVIEW                         |
+==============================================================================+


                              +-------------+
                              |   LOADING   |
                              +-------------+
                                    |
                                    v
                        +-----------------------+
                        |    INITIALIZATION     |
                        | - Load DLL            |
                        | - Request interfaces  |
                        | - Initialize          |
                        | - Register callbacks  |
                        | - GetWriteableDir     |
                        | - GetProperties       |
                        | - LoadingComplete     |
                        +-----------------------+
                                    |
                   +----------------+----------------+
                   |                                 |
              [memento exists]              [no memento]
                   |                                 |
                   v                                 v
            +-------------+                  +-------------+
            |  RECOVERY   |                  |    IDLE     |<------------+
            +-------------+                  +-------------+             |
                   |                               |                     |
                   |    +------------------------->|                     |
                   |    |                          |                     |
                   |    |     (START pressed)      |                     |
                   |    |                          v                     |
                   |    |                  +---------------+             |
                   |    |                  | ASK_CONTINUE  |             |
                   +----+----------------->+---------------+             |
                                                   |                     |
                                      +------------+------------+        |
                                      |                         |        |
                                 [allow]                   [deny]        |
                                      |                         |        |
                                      v                         v        |
                           +------------------+          +-----------+   |
                           | START_GAME_CYCLE |          |   EXIT    |   |
                           +------------------+          +-----------+   |
                                      |                                  |
                                      v                                  |
                           +------------------+                          |
                           | RESERVE_STAKE    |                          |
                           +------------------+                          |
                                      |                                  |
                                      v                                  |
                           +------------------+                          |
                           | GET_RANDOM       |<-----------+             |
                           +------------------+            |             |
                                      |                    |             |
                                      v                    |             |
                           +------------------+            |             |
                           | SET_CHECKPOINT   |------------+             |
                           | (PRIMARY)        |    (more randomness      |
                           +------------------+     needed for features) |
                                      |                                  |
                                      v                                  |
                           +------------------+                          |
                           | COMMIT_STAKE     |                          |
                           +------------------+                          |
                                      |                                  |
                         +------------+------------+                     |
                         |                         |                     |
                    [has win]                 [no win]                   |
                         |                         |                     |
                         v                         |                     |
              +--------------------+               |                     |
              |   FEATURE LOOP?    |               |                     |
              +--------------------+               |                     |
                    /        \                     |                     |
                  YES        NO                    |                     |
                   |          |                    |                     |
                   v          |                    |                     |
            +------------+    |                    |                     |
            | GET_RANDOM |    |                    |                     |
            | CHECKPOINT |    |                    |                     |
            | (FEATURE)  |    |                    |                     |
            +------------+    |                    |                     |
                   |          |                    |                     |
                   +----+-----+                    |                     |
                        |                         |                     |
                        v                         |                     |
              +--------------------+               |                     |
              |   RISK OFFERED?    |               |                     |
              +--------------------+               |                     |
                    /        \                     |                     |
                  YES        NO                    |                     |
                   |          |                    |                     |
                   v          |                    |                     |
            +------------+    |                    |                     |
            | RISK_STATE |    |                    |                     |
            | GET_RANDOM |    |                    |                     |
            | CHECKPOINT |    |                    |                     |
            | (GAMBLE)   |    |                    |                     |
            +------------+    |                    |                     |
                   |          |                    |                     |
              +----+----+     |                    |                     |
              |         |     |                    |                     |
          [win]     [lose]    |                    |                     |
              |         |     |                    |                     |
              v         v     |                    |                     |
         [risk      +---+     |                    |                     |
          again?]   |         |                    |                     |
            |       |         |                    |                     |
            +-------+---------+                    |                     |
                        |                         |                     |
                        v                         |                     |
              +--------------------+               |                     |
              | AWARD_WINNINGS?    |               |                     |
              | (only if win > 0)  |               |                     |
              +--------------------+               |                     |
                        |                         |                     |
                        +-----------+-------------+                     |
                                    |                                   |
                                    v                                   |
                           +------------------+                          |
                           | END_GAME_CYCLE   |                          |
                           +------------------+                          |
                                    |                                   |
                                    v                                   |
                           +------------------+                          |
                           | ASK_CONTINUE     |                          |
                           +------------------+                          |
                                    |                                   |
                       +------------+------------+                      |
                       |                         |                      |
                  [allow]                   [deny]                      |
                       |                         |                      |
                       +-------------------------+----------------------+
                                                 |
                                                 v
                                          +-----------+
                                          |   EXIT    |
                                          +-----------+


+==============================================================================+
|                         CALL RESPONSE REQUIREMENTS                           |
+==============================================================================+

+----------------------------+-------------------+---------------------------+
|          CALL              |    ON SUCCESS     |        ON ERROR           |
+----------------------------+-------------------+---------------------------+
| AskContinue                | int==1: continue  | int==0/error: EXIT        |
|                            | int==0: exit      | (graceful, log, no msg)   |
+----------------------------+-------------------+---------------------------+
| StartGameCycle             | Save GCID         | EXIT (graceful, log,      |
|                            | Continue          | no message)               |
+----------------------------+-------------------+---------------------------+
| ReserveStake               | Save token        | EXIT (graceful, log,      |
| ReserveAdditionalStake     | Start animation   | no message)               |
+----------------------------+-------------------+---------------------------+
| GetRandomInt32             | Calculate outcome | Show RNG error message    |
| GetRandomInts32            | Save to memento   | 5 sec, then EXIT          |
|                            |                   | DO NOT end game cycle     |
+----------------------------+-------------------+---------------------------+
| SetCheckpoint              | Continue          | EXIT (graceful, log,      |
|                            |                   | no message)               |
+----------------------------+-------------------+---------------------------+
| CommitStake                | Continue          | EXIT (graceful, log,      |
|                            |                   | no message)               |
+----------------------------+-------------------+---------------------------+
| AwardWinnings              | Continue to End   | EXIT (graceful, log,      |
|                            |                   | DO NOT end game cycle,    |
|                            |                   | no message)               |
+----------------------------+-------------------+---------------------------+
| EndGameCycle               | Clear memento     | EXIT (graceful, log,      |
|                            | Continue          | no message)               |
+----------------------------+-------------------+---------------------------+
| Cashout                    | Wait for exit     | Show error 5 sec with     |
|                            | event             | AMOUNT, then exit to menu |
+----------------------------+-------------------+---------------------------+
| SetLimits                  | Continue          | EXIT (graceful, log,      |
|                            |                   | no message)               |
+----------------------------+-------------------+---------------------------+
| RollbackStake              | Continue (credit  | EXIT (graceful, log,      |
|                            | restored)         | no message)               |
+----------------------------+-------------------+---------------------------+
| Exiting                    | Continue shutdown | Log (don't stop exit)     |
+----------------------------+-------------------+---------------------------+
| heartbeat                  | Reset timer       | Continue (not critical)   |
+----------------------------+-------------------+---------------------------+


+==============================================================================+
|                            TIMING CONSTRAINTS                                |
+==============================================================================+

| Constraint                                    | Value        |
|-----------------------------------------------|--------------|
| heartbeat interval                            | ~15 seconds  |
| heartbeat timeout (game killed)               | 25 seconds   |
| Initial load time (menu to playable)          | < 5 seconds  |
| Subsequent load time                          | < 3 seconds  |
| Exit timeout (after Exiting call)             | 5000 ms      |
| Cashout error message display                 | 5 seconds    |
| RNG error message display                     | 5 seconds    |

+==============================================================================+
|                            GAME LIMITS                                       |
+==============================================================================+

| Limit                                         | Value              |
|-----------------------------------------------|--------------------|
| Minimum stake                                 | 50 cents (€0.50)   |
| Maximum stake                                 | 1000 cents (€10)   |
| Maximum win                                   | 500000 cents (€5000)|
| Tax threshold (minThresh)                     | 20000 cents (€200) |
| Tax rate                                      | 20%                |
| GetRandomInts32 max numbers per call          | 32                 |
| GetRandomInts32 max randomness                | 2^1024             |

```

---

## Logging Requirements

```
+==============================================================================+
|                           LOGGING REQUIREMENTS                               |
+==============================================================================+

FILE NAMING:
    Betting activity log: itboxlogYYYYMMDDbetevent.log
    Example: itboxlog20240215betevent.log

LOCATION:
    - All logs MUST be in working directory (from GetWriteableDirectory)
    - NEVER write to Windows temp folders or other locations

LOG CONTENT (required):
    - Game loading info (name, version, timestamp)
    - Credit at start/end of session
    - All stake changes
    - All button presses
    - Reel positions for each spin (base game, free spins, extra spins)
    - Win amounts per spin
    - Feature triggers and types
    - Free/Extra spin counters (e.g., "[3/10]")
    - Retrigger events
    - Risk game outcomes
    - Event receipts (credit changes, limits, etc.)
    - Exit reason (menu, cashout, limit reached, error, kill message)
    - API call failures

FORMAT:
    - Each line MUST be timestamped to MILLISECONDS
    - Format: DD/MM/YYYY [HH:MM:SS:mmm]: message
    - Example: 01/05/2024 [11:37:47:122]: Game (cycle) started

RESTRICTIONS:
    - NEVER log random numbers (except in obfuscated memento)
    - NEVER use words: Debug, Test, Diagnostic, TODO, HACK
    - File names must not imply unfinished/test code

MAINTENANCE:
    - Prune logs older than 60 days
    - Append to existing daily log (don't create new file per execution)
    - Max 200 files, 200MB total in working directory
```

---

## API Reference Quick Summary

```
+==============================================================================+
|                          API CALLS QUICK REFERENCE                           |
+==============================================================================+

LEGION ITALY INTERFACE (LegionItalyInterface)
---------------------------------------------
heartbeat(cb, userData)
GetWriteableDirectory(cb, userData)
GetProperties(cb, userData)
LoadingComplete(cb, userData)
GetCredit(cb, userData)
AskContinue(cb, userData)
StartGameCycle(cb, userData, gameCycleId)
ReserveStake(cb, userData, amount)
ReserveAdditionalStake(cb, userData, amount)
GetRandomInt32(cb, userData, lower, upper)
GetRandomInts32(cb, userData, lower, upper, count, results)
SetCheckpoint(cb, userData, phaseSummary, phaseInfo)
CommitStake(cb, userData, token)
RollbackStake(cb, userData, token)
AwardWinnings(cb, userData, amount)
EndGameCycle(cb, userData, summary, phaseInfo)
Cashout(cb, userData)
SetLimits(cb, userData, spendLimit, timeLimit)
Exiting(cb, userData)

MANDATORY EVENT REGISTRATIONS:
OnCreditChangedEvent(cb, userData)
OnExitDeferredEvent(cb, userData)
OnExitEvent(cb, userData)
OnLimitsEvent(cb, userData)
OnCashoutEndEvent(cb, userData)

OPTIONAL EVENT REGISTRATIONS:
OnTaxEvent(cb, userData)              // v2.20.0.0+ only, when LegacyTaxPopup=FALSE

CABINET BUTTONS INTERFACE (CabinetButtonsInterface)
---------------------------------------------------
Initialize()
processCallbacks()
SetButtonCallback(cb, userData)
SetLights(lightMask)                  // 32-bit mask
shutdown()

ADMIN INTERFACE (adminInterface)
--------------------------------
Initialize()
processCallbacks()
RequestInterface(name)
shutdown()
```

---

*Document generated based on Italian Development Guide v1.5 for OGAPI v2.20.0.0*
