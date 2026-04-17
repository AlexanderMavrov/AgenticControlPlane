# Visual QA Rules — Alpha Family (извлечени от burning_hot_coins)

**Извлечени от:** `C:\Workspace\games\resources\burning_hot_coins\`
**Дата:** 2026-04-16
**Резолюция:** 1920x1080

---

## Rule Categories

Всяко правило има **category**, която определя нивото на доверие:

| Category | Означение | Описание | False positive risk |
|----------|-----------|----------|-------------------|
| **integrity** | `[I]` | Cross-reference — файлове/ключове съществуват | Нулев |
| **consistency** | `[C]` | Елементите са консистентни помежду си (symmetry, alignment, spacing) | Нисък |
| **convention** | `[W]` | Стойност отговаря на очаквана конвенция, извлечена от reference game. **Reporting level: WARNING** — може да е intentional design choice. | Висок |

**Как се ползва:**
- `[I]` и `[C]` findings → **errors** (почти сигурно бъгове)
- `[W]` findings → **warnings** (нестандартно, но може да е by design)

---

## Layout zones (1920x1080)

| Зона | Y range | Описание |
|------|---------|----------|
| Reel area | 0–~850 | Game background + reels grid |
| Panel | ~850–1080 | Bottom panel background |
| Status bar | ~900–930 | Status messages, GAME OVER, 18+ |
| Buttons | ~950–1000 | SELECT GAME, HELP, Language, ADM, etc. |
| Bar labels | ~1043 | CREDIT, COINS, BET, WIN image labels |
| Bar values | ~1048 | Text amounts (credit/coins/bet/win) |

---

# A. GAME BACKGROUND & FRAME

## Rule A1: Background image — alpha `[W]`

**Елемент:** `GameBackgroundView.json → image_game_background`
**Правило:** `color.a` трябва да е 255 (непрозрачен). Semi-transparent background причинява видим teal/dark bleed-through.
**Detection:** `color.a < 255` → flag
**Severity:** Medium (видимо при сравнение)
**Ref value:** `color: {r:255, g:255, b:255, a:255}` (очаквано)

## Rule A2: Background image — color tint `[W]`

**Елемент:** `GameBackgroundView.json → image_game_background`
**Правило:** `color` трябва да е чисто бяло `{r:255, g:255, b:255}` (без tint). Non-white color tint-ва целия background/frame.
**Detection:** `r != 255 || g != 255 || b != 255` → flag
**Severity:** High (променя цвета на целия frame)

## Rule A3: Panel background — gap detection `[C]`

**Елемент:** `GameBackgroundView.json → image_panel_background`
**Правило:** Panel-ът трябва да започва непосредствено след reel area — без видим gap.
**Detection:**
- Изчисли reel area bottom: `reelAreaY + visibleRows * reelStepY` (от idata ReelsView)
  - За burning_hot_coins: `32 + 3 * 270 = 842`
- Panel y трябва да е ≤ reel area bottom + margin (~10px)
- Ако `panel.y - reelBottom > 10` → flag gap
**Ref value:** `y: 850` (очаквано, без gap)
**Severity:** High (видим teal gap)

## Rule A4: Panel background — full width `[C]`

**Елемент:** `GameBackgroundView.json → image_panel_background`
**Правило:** Panel-ът трябва да започва от x:0 (пълна ширина).
**Detection:** `position.x != 0` → flag
**Ref value:** `x: 0`

## Rule A5: 18+ icon — position `[C]`

**Елемент:** `GameBackgroundView.json → image_18+`
**Правило:** Трябва да е в долен десен ъгъл на status bar zone.
**Detection:**
- `x` трябва да е близо до `screenWidth` (1920), с alignment MiddleRight
- `y` трябва да е в status bar zone (~900-930)
**Ref value:** `x: 1875, y: 904`

## Rule A6: Regulatory elements — not hidden `[I]`

**Елемент:** `GameBackgroundView.json → image_18+` (и всички regulatory елементи)
**Правило:** Регулаторни елементи (18+ бадж) не трябва да са скрити чрез `"hidden": true`. Липсата на 18+ индикация е регулаторно нарушение.
**Detection:** `hidden === true` на елемент с ID `image_18+` или подобен regulatory елемент → flag
**Severity:** Critical (регулаторно изискване)
**Ref value:** `hidden` трябва да е `false` или да липсва (default: visible)

## Rule A7: Background/panel — no unexpected rotation `[C]`

**Елемент:** `GameBackgroundView.json → image_panel_background, image_game_background`
**Правило:** Background и panel елементите не трябва да имат rotation != 0. Дори малък ъгъл (напр. 2°) причинява видимо наклоняване на панела.
**Detection:** `rotation != 0 && rotation != undefined` → flag
**Severity:** High (видимо наклоняване на целия панел)
**Ref value:** `rotation: 0` (или без rotation property)

---

# B. KNOBS (Line count indicators)

## Rule B1: Knobs — symmetric positions `[C]`

**Елементи:** `KnobsView.json → image_knobs_left, image_knobs_right`
**Правило:** Left и right knobs трябва да са огледално симетрични спрямо центъра на екрана (x=960) и с еднакъв y.
**Detection:**
- `|right.x - (screenWidth - left.x)| > 5` → flag x asymmetry
- `|right.y - left.y| > 5` → flag y asymmetry
**Ref values:** left: `x:69, y:440`, right: `x:1851, y:440` (очаквано)
**Severity:** High (видима асиметрия)

## Rule B2: Knobs — same rssKey `[C]`

**Елементи:** `KnobsView.json → image_knobs_left, image_knobs_right`
**Правило:** Двата knob-а трябва да реферират един и същ rssKey (освен ако не са изрично различни).
**Detection:** `left.rssKey != right.rssKey` → flag
**Ref value:** и двата: `IMAGE_REEL_ACTIVE_LINES_10`

## Rule B3: Knobs — within reel area `[C]`

**Елементи:** `KnobsView.json → all elements`
**Правило:** Knobs трябва да са в reel area zone (y < panel start).
**Detection:** `y > panelStartY` → flag
**Ref value:** `y: 440` (в рамките на reel area)

## Rule B4: Knobs — expected alignment `[C]`

**Елементи:** `KnobsView.json → image_knobs_left, image_knobs_right`
**Правило:** Knob елементите трябва да използват `MiddleCenter` alignment. Грешен alignment (напр. `TopLeft`) измества визуално елемента спрямо очакваната позиция.
**Detection:** `alignment != "MiddleCenter"` → flag
**Severity:** High (елементът е визуално изместен)
**Ref value:** `alignment: "MiddleCenter"`

---

# C. CREDIT BAR

## Rule C1: Credit text amount — no explicit color `[W]`

**Елемент:** `CreditBarView.json → text_amount`
**Правило:** Primary credit amount трябва да ползва rssStyleId без explicit color override. Explicit color (особено non-white) е аномалия.
**Detection:** Element has `color` property → flag. Особено: `color.g == 255 && color.r == 0` (зелен) → critical.
**Severity:** Critical (зелен текст е очевиден бъг)

## Rule C2: Credit label — uniform scale `[W]`

**Елемент:** `CreditBarView.json → image_label, image_label_max`
**Правило:** Scale трябва да е uniform (x == y) или default (1.0, 1.0).
**Detection:** `scale.x != scale.y` → flag deformation
**Severity:** Critical (деформиран label е очевиден)
**Ref value:** `scale: {x:1.0, y:1.0}` (очаквано)

## Rule C3: Credit bar — _min/_max consistency `[C]`

**Елементи:** `CreditBarView.json → text_amount_min, text_amount_max, image_label_min, image_label_max`
**Правило:** `_min` и `_max` варианти са за min/max bet display. `_max` трябва да има чисто бял цвят. `_min` е gray (128,128,128).
**Detection:**
- `text_amount_max.color != {255,255,255,255}` → flag
- `image_label_max.color != {255,255,255,255}` → flag
- `image_label_max.scale` non-uniform → flag
**Ref values:** max color: `{r:255, g:255, b:255, a:255}`, max scale: `{x:1.0, y:1.0}`

## Rule C4: Credit bar — position in bar zone `[C]`

**Елементи:** `CreditBarView.json → all`
**Правило:** Primary елементите (text_amount, image_label) трябва да са в bar zone.
**Detection:**
- `text_amount.position.y` трябва да е ~1048 (bar values zone)
- `image_label.position.y` трябва да е ~1043 (bar labels zone)
- Ако primary елементи са извън bar zone → flag

---

# D. COINS BAR

## Rule D1: Coins text — pure white color `[W]`

**Елемент:** `CoinsBarView.json → text_amount_max`
**Правило:** Цветът трябва да е чисто бял (255,255,255), не тинтиран.
**Detection:**
- `max(r,g,b) == 255 && min(r,g,b) < 245` → flag warm/cool tint
- Severity зависи от delta: `255 - min(r,g,b)`
**Ref value:** `{r:255, g:255, b:255}` (очаквано)
**Severity:** Low (субтилен tint)

## Rule D2: Coins bar — consistency with credit bar `[C]`

**Елементи:** `CoinsBarView.json vs CreditBarView.json`
**Правило:** Equivalent елементи (text_amount_max, image_label_max) трябва да имат consistent styling.
**Detection:**
- Сравни color values между bars
- Сравни scale values между bars
- Inconsistency → flag

## Rule D3: Coins bar — x position ordering `[C]`

**Елемент:** `CoinsBarView.json → text_amount`
**Правило:** Coins bar трябва да е вдясно от credit bar и вляво от bet bar.
**Detection:** `credit.x < coins.x < bet.x` → OK; нарушение → flag
**Ref values:** credit x:~490-513, coins x:~710-745, bet x:~998

---

# E. BET BAR

## Rule E1: Bet bar — minimal structure `[I]`

**Елементи:** `BetBarView.json → text_bet_amount, image_bet`
**Правило:** Bet bar-ът трябва да има поне text amount и image label.
**Detection:** Липсва `text_bet_amount` или `image_bet` → flag
**Ref value:** text at `x:998, y:1048`, image at `x:998, y:1043`

## Rule E2: Bet bar — aligned with other bars `[C]`

**Елементи:** `BetBarView.json`
**Правило:** Text и label y-координати трябва да съвпадат с credit и coins bars.
**Detection:** `|bet.text.y - credit.text.y| > 2` → flag
**Ref value:** Всички bars: text y ≈ 1048, label y ≈ 1043

## Rule E3: Bet up/down buttons — symmetric around bet bar `[C]`

**Елементи:** `BetUpSwButtonView.json, BetDownSwButtonView.json`
**Правило:** BetUp и BetDown бутоните трябва да са симетрични около bet bar центъра.
**Detection:**
- `|betUp.x - bet.x| ≈ |bet.x - betDown.x|` (tolerance ±10px)
- `|betUp.y - betDown.y| < 5` (same row)
**Ref values:** betDown: `x:865, y:990`, betUp: `x:1082, y:989`, bet center: `x:998`

## Rule E4: Bar label — x co-located with bar text `[C]`

**Елементи:** `BetBarView.json → image_bet, text_bet_amount` (и всички bar views)
**Правило:** Label image-ът на bar-а трябва да е на приблизително същата x-координата като text amount-а на същия bar. Ако label-ът е изместен на x-координатата на друг bar (напр. bet label на x:1344 вместо x:998), двата label-а се припокриват.
**Detection:** `|label.x - text.x| > 50` → flag (label е твърде далеч от своя text)
**Severity:** Critical (label се припокрива с друг bar)
**Ref value:** Label и text в рамките на ±50px по x

---

# F. WIN BAR

## Rule F1: Win bar — text style uses dedicated win style `[I]`

**Елемент:** `CreditsWinBarView.json → text_win_amount`
**Правило:** Win amount трябва да ползва `STYLE_PANEL_PREMIER_BAR_WIN` (по-голям font от credit).
**Detection:** `rssStyleId != "STYLE_PANEL_PREMIER_BAR_WIN"` → flag
**Ref value:** rssStyleId: `STYLE_PANEL_PREMIER_BAR_WIN` (size 77 vs credit size 58)

## Rule F2: Win bar — rightmost position `[C]`

**Елемент:** `CreditsWinBarView.json → text_win_amount`
**Правило:** Win bar трябва да е най-вдясно от четирите bars.
**Detection:** `win.x < bet.x` → flag
**Ref value:** `x: 1344` (> bet x: 998)

## Rule F3: Win label — multiple rssKeys `[I]`

**Елемент:** `CreditsWinBarView.json → image_win_label`
**Правило:** Win label трябва да има поне 2 rssKeys (WIN и WINNER PAID states).
**Detection:** `rssKeys.length < 2` → flag (може да липсва state)
**Ref value:** `["IMAGE_PANEL_PREMIER_LABEL_WIN", "IMAGE_PANEL_PREMIER_LABEL_WINNER_PAID"]`

---

# G. STATUS LINE

## Rule G1: Mid-status elements — consistent position `[C]`

**Елементи:** `StatusLineView.json → all image_status_mid_*`
**Правило:** ВСИЧКИ mid-status елементи трябва да споделят еднакви x,y координати.
**Detection:** Групирай по prefix `image_status_mid_*`. Ако един елемент има различен y → flag.
**Ref value:** Всички `x:960, y:904` (centerX, status bar Y)
**Severity:** High (displaced status text навлиза в друга зона)

## Rule G2: Status line — within status zone `[C]`

**Елементи:** `StatusLineView.json → all non-empty elements`
**Правило:** Всички status елементи трябва да са в status bar zone (y: ~900-930).
**Detection:** `y > 940 || y < 880` → flag (извън зоната)
**Exception:** `image_status_mid_none` може да няма позиция (empty rssKey)

## Rule G3: Left/right status — correct sides `[C]`

**Елементи:** `StatusLineView.json → image_status_left_*, image_status_right_*`
**Правило:** Left status трябва да е в лявата половина (x < 960), right — в дясната (x > 960).
**Detection:** `left.x > 960 || right.x < 960` → flag
**Ref values:** left: `x:48`, right gamble: `x:1745`, right game over: `x:1740`

## Rule G4: idata StatusLineView — midPoint consistency `[C]`

**Елемент:** `idata/1920x1080/StatusLineView.json → midPoint`
**Правило:** midPoint трябва да съвпада с позицията на mid-status елементите в v/ StatusLineView.
**Detection:** `|midPoint.x - statusMid.x| > 5 || |midPoint.y - statusMid.y| > 5` → flag
**Ref values:** midPoint: `{x:960, y:905}`, v/ status mid: `{x:960, y:904}` (1px tolerance OK)

---

# H. BUTTONS (SwButton Views)

## Rule H1: Button — requires 3 rssKeys `[I]`

**Елементи:** All `*SwButtonView.json → button_*`
**Правило:** Всеки Button елемент трябва да има точно 3 rssKeys: [enabled, pressed, disabled].
**Detection:** `rssKeys.length != 3` → flag
**Exception:** Buttons без rssKeys (touch-only, напр. StopSingleReelSwButtonView, WheelStartSwButtonView) са OK.

## Rule H2: Button + frame — co-located `[C]`

**Елементи:** `*SwButtonView.json → button_*, frame`
**Правило:** Когато view-то има и button и frame елемент, те трябва да споделят еднаква позиция.
**Detection:** `|button.x - frame.x| > 2 || |button.y - frame.y| > 2` → flag
**Ref pattern:** ExitGame: button `{10, 950}`, frame `{10, 950}` ✓

## Rule H3: Panel buttons — within button zone `[C]`

**Елементи:** ExitGame, Info, Language, TakeCoins, Responsible, SoundVolume buttons
**Правило:** Всички panel buttons трябва да са в button zone (y: ~940-1000).
**Detection:** `y < 930 || y > 1010` → flag
**Ref values:** ExitGame `y:950`, Info `y:950`, Language `y:950`, TakeCoins `y:951`, Responsible `y:952`, Volume `y:905`
**Note:** SoundVolume е по-горе (y:905) — в status bar zone. Това може да е валиден pattern.

## Rule H4: Panel buttons — left/right distribution `[C]`

**Елементи:** Panel buttons
**Правило:** Бутоните се разпределят: лява група (SELECT GAME, HELP) и дясна група (Language, ADM/Responsible, Volume).
**Detection:**
- Left group: `x < 400` → ExitGame(10), Info(187) ✓
- Right group: `x > 1500` → Language(1560), Responsible(1739), Volume(1811) ✓
- Бутон от лявата група с `x > 960` → flag
**Severity:** Medium

## Rule H5: Panel buttons — no overlap `[C]`

**Елементи:** All panel buttons
**Правило:** Бутоните не трябва да се застъпват (позиции трябва да са разстояни).
**Detection:** За бутони в една група, сортирай по x. Ако `button[i+1].x - button[i].x < 50` → possible overlap (зависи от image size).
**Ref left group spacing:** Info.x - ExitGame.x = 177px ✓

---

# I. REEL GRID (idata)

## Rule I1: Symbol count matches math file `[I]`

**Елементи:** `idata/ReelsView.json → symbolsConfig` vs `math/var_*.json → symbolNames`
**Правило:** Броят на символите в symbolsConfig трябва да съвпада с math file.
**Detection:** `symbolsConfig.length != symbolNames.length` → flag
**Ref value:** 11 символа (0-10)

## Rule I2: Symbol IDs are sequential `[I]`

**Елементи:** `idata/ReelsView.json → symbolsConfig`
**Правило:** Symbol IDs трябва да са последователни от 0 до N-1.
**Detection:** Sorted IDs != [0, 1, 2, ..., N-1] → flag

## Rule I3: Every symbol has valid rssId `[I]`

**Елементи:** `idata/ReelsView.json → symbolsConfig[*].rssId`
**Правило:** Всеки rssId трябва да съществува в RssImagesData.json.
**Detection:** rssId not found in images manifest → flag
**Ref pattern:** `IMAGE_REEL_CHERRY` → `art/.../cherry.dds` ✓

## Rule I4: Reel grid dimensions match math `[I]`

**Елементи:** `idata/ReelsView.json → visibleCols, visibleRows` vs `math → reelsCount, rowsCount`
**Правило:** Grid dimensions трябва да съвпадат.
**Detection:** `visibleCols != reelsCount || visibleRows != rowsCount` → flag
**Ref value:** 5x3

## Rule I5: Reel step consistency across idata files `[C]`

**Елементи:** `idata/ReelsView.json, idata/LinesView.json, idata/WinFiguresView.json`
**Правило:** reelAreaX, reelAreaY, reelStepX, reelStepY трябва да съвпадат между файловете.
**Detection:** Разлика в стойностите между файловете → flag
**Ref values:** `reelAreaX:140, reelAreaY:32, reelStepX:335, reelStepY:270`

## Rule I6: Reel area fits within screen `[C]`

**Елементи:** `idata/ReelsView.json`
**Правило:** Reel grid трябва да се побира на екрана.
**Detection:**
- `reelAreaX + visibleCols * reelStepX > screenWidth` → flag
- `reelAreaY + visibleRows * reelStepY > panelStartY` → flag
**Ref calc:** 140 + 5*335 = 1815 < 1920 ✓, 32 + 3*270 = 842 < ~850 ✓

---

# J. WIN FIGURES & LINES (idata)

## Rule J1: WinFigures — keys for all symbols `[I]`

**Елемент:** `idata/WinFiguresView.json → winFiguresRssKeys`
**Правило:** Трябва да има entry за всяко symbol ID (0 до N-1).
**Detection:** Missing key for any ID → flag
**Ref value:** Keys "0" through "10" → ANIM_REEL_* 

## Rule J2: WinFigures RSS keys exist in animations `[I]`

**Елемент:** `idata/WinFiguresView.json → winFiguresRssKeys`
**Правило:** Всеки ANIM_REEL_* ключ трябва да съществува в RssImagesSeqData.json.
**Detection:** Key not found in animations manifest → flag

## Rule J3: Lines — count matches math `[I]`

**Елемент:** `idata/LinesView.json → lines`
**Правило:** Броят линии трябва да е >= броят дефинирани в math файла.
**Detection:** `lines.length < math.lines.length` → flag
**Ref value:** 10 lines

## Rule J4: Lines — all imageIds exist `[I]`

**Елемент:** `idata/LinesView.json → lines[*].imageId`
**Правило:** Всеки imageId трябва да съществува в RssImagesData.json.
**Detection:** imageId not found → flag
**Ref pattern:** `IMAGE_WINLINES_LINE_01` through `_10`

## Rule J5: Lines — win sounds for all symbols `[I]`

**Елемент:** `idata/LinesView.json → winFiguresDefaultSoundRssKeys`
**Правило:** Всяко symbol ID трябва да има sound key (може да е empty string за wild).
**Detection:** Missing key → flag; empty string е OK за wild (ID 8)
**Ref:** ID 8 (WILD): `""` — OK (wild няма собствен win sound)

## Rule J6: WinSquare RSS keys exist `[I]`

**Елемент:** `idata/LinesView.json → winSquareRssKeys`
**Правило:** Всеки win square image трябва да съществува в RssImagesData.
**Detection:** Key not found → flag
**Ref:** `IMAGE_WINLINES_SQUARE_01` through `_10`

---

# K. GAMBLE ROUND

## Rule K1: Gamble card elements — centered `[C]`

**Елементи:** `GambleRoundView.json → image_ace_of_*`
**Правило:** Всички card images (ace of spades/hearts/clubs/diamonds) трябва да споделят еднаква позиция (center).
**Detection:** Различни позиции между card images → flag
**Ref value:** Всички `x:959.5, y:372`

## Rule K2: History cards — evenly spaced `[C]`

**Елементи:** `GambleRoundView.json → image_history_card_*`
**Правило:** History card-овете трябва да са равномерно разстояни по x (consistent step).
**Detection:** Изчисли step: `card[i+1].x - card[i].x`. Ако step-ът варира > 5px → flag.
**Ref values:** 1302, 1397, 1492, 1587, 1682, 1777 → step ≈ 95px ✓
**Note:** Всички y:317 (same row) ✓

## Rule K3: Gamble amount/to-win — symmetric `[C]`

**Елементи:** `GambleRoundView.json → image_amount + text_amount vs image_to_win + text_to_win`
**Правило:** Amount (лява) и To Win (дясна) трябва да са симетрични.
**Detection:** `|amount.x + to_win.x - screenWidth| > 10` → flag
**Ref values:** amount x:324, to_win x:1586 → 324+1586=1910 ≈ 1920 ✓

## Rule K4: Gamble overlay — full screen coverage `[C]`

**Елемент:** `GambleRoundOverlayView.json → image_outro_overlay`
**Правило:** Overlay scale трябва да покрива целия екран (scale * pattern_size ≥ screen_size).
**Detection:** `scale.x * patternW < screenWidth || scale.y * patternH < screenHeight` → flag
**Ref value:** 4px * 480 = 1920 ✓, 4px * 270 = 1080 ✓

---

# L. WHEEL ROUND

## Rule L1: Wheel center — all elements at same point `[C]`

**Елементи:** `WheelRoundView.json → wheel_base, sectors, shadow, pin, edge, arrow`
**Правило:** Всички wheel елементи трябва да споделят центъра на колелото.
**Detection:** Елемент с position различна от wheel center → flag
**Ref value:** Всички `x:960, y:478, alignment:MiddleCenter`

## Rule L2: Wheel sector text — same position and fitBox `[C]`

**Елементи:** `WheelRoundView.json → text_sector_*`
**Правило:** Всички sector texts трябва да имат еднакви position, fitBox, style.
**Detection:** Различия между sector texts → flag
**Ref values:** Всички `x:960, y:140, fitBox:{w:46, h:260}, style:STYLE_WHEEL_YELLOW_DIGITS`

## Rule L3: Wheel panel — position `[C]`

**Елемент:** `WheelRoundView.json → image_game_panel_background_wheel`
**Правило:** Wheel panel трябва да е в долната част на екрана.
**Detection:** `y < 900 || y > 960` → flag
**Ref value:** `y: 944`

---

# M. MENUS

## Rule M1: Language menu — items evenly spaced `[C]`

**Елементи:** `LanguageMenuView.json → image_*_background`
**Правило:** Menu items трябва да са равномерно разстояни по y.
**Detection:** Inconsistent y-spacing → flag
**Ref values:** italian: `y:27`, english: `y:112` → step: 85px

## Rule M2: Language menu — button + border + label aligned `[C]`

**Елементи:** `LanguageMenuView.json → button_*, image_*_border, image_*_flagborder, image_*_label`
**Правило:** За всеки language item: button, flagborder и label трябва да са на един и същ ред (same y).
**Detection:** `|button.y - flagborder.y| > 2 || |button.y - label.y| > 20` → flag
**Ref pattern:** Italian: button y:69, flagborder y:69, label y:69 ✓

## Rule M3: Bet menu — button positions symmetric `[C]`

**Елементи:** `BetMenuView.json → button_bet_up, button_bet_down`
**Правило:** Up/down бутони трябва да са симетрични около текста.
**Detection:** `|up.x + down.x - 2*text.x| > 20` → flag
**Ref values:** down: `x:105`, up: `x:500`, text: `x:303` → 105+500=605, 2*303=606 ✓

---

# N. CROSS-CUTTING RULES

## Rule N1: All rssKey references must exist `[I]`

**Обхват:** ВСИЧКИ view JSON файлове
**Правило:** Всеки `rssKey` и елемент от `rssKeys[]` трябва да съществува в RssImagesData, RssImagesSeqData, RssSoundsData или RssRawData.
**Detection:** Key not found in any manifest → flag
**Exception:** Empty string `""` е OK (intentionally empty, напр. status_mid_none)

## Rule N2: All rssStyleId references must exist `[I]`

**Обхват:** ВСИЧКИ view JSON файлове
**Правило:** Всеки `rssStyleId` трябва да съществува в RssTextStylesData.json.
**Detection:** Style not found → flag

## Rule N3: No duplicate element IDs within a view `[I]`

**Обхват:** Всеки view JSON
**Правило:** Element IDs трябва да са уникални в рамките на view-то.
**Detection:** Duplicate ID → flag

## Rule N4: Element type determines required properties `[I]`

**Обхват:** Всички елементи
**Правило:** Зависи от `type`:
- `Image` → трябва да има `rssKey` или `rssKeys`
- `Text` → трябва да има `rssStyleId`
- `Button` → трябва да има `rssKeys` (3 items) или `touchArea`
- `Anim` → трябва да има `rssKey`
- `Dummy` → няма изисквания (layout anchor)
**Detection:** Missing required property → flag

## Rule N5: Resolution consistency `[I]`

**Обхват:** `RssElementsListData.json`
**Правило:** Всички view paths трябва да са за една и съща resolution.
**Detection:** Mixed resolutions → flag

## Rule N6: Bar values alignment `[C]`

**Обхват:** CreditBarView, CoinsBarView, BetBarView, CreditsWinBarView
**Правило:** Primary text amounts трябва да споделят еднакъв y-координат.
**Detection:** `max(y) - min(y) > 2` across bar text amounts → flag
**Ref value:** Всички text amounts: `y ≈ 1048`

## Rule N7: Bar labels alignment `[C]`

**Обхват:** CreditBarView, CoinsBarView, BetBarView, CreditsWinBarView
**Правило:** Label images трябва да споделят еднакъв y-координат.
**Detection:** `max(y) - min(y) > 2` across bar labels → flag
**Ref value:** Всички labels: `y ≈ 1043-1044`

## Rule N9: Text fitBox — minimum readable size `[C]`

**Обхват:** Всички Text елементи с `fitBox` property
**Правило:** `fitBox` размерите не трябва да са прекалено малки — силно намален fitBox (напр. от 278x64 на 80x20) компресира текста до нечетимост.
**Detection:**
- `fitBox.w < 100 && element has expected larger fitBox` → flag
- Или сравни с reference: ако fitBox е < 30% от очаквания размер → flag
**Severity:** Critical (текстът е нечетим)
**Ref values:** Coins text fitBox: `{w:278, h:64}` (очаквано). Стойности под `{w:100, h:30}` са подозрителни за primary bar text.

## Rule N8: Bar x-ordering `[C]`

**Обхват:** All bar views
**Правило:** Bars трябва да са подредени ляво→дясно: Credit → Coins → Bet → Win
**Detection:** `credit.x >= coins.x || coins.x >= bet.x || bet.x >= win.x` → flag
**Ref values:** credit ~500, coins ~720, bet ~998, win ~1344

---

# O. TOUCH AREAS

## Rule O1: Reel stop buttons — even spacing `[C]`

**Елементи:** `StopSingleReelSwButtonView.json → button_reel_*`
**Правило:** Touch areas трябва да са равномерно разстояни и с еднакъв размер.
**Detection:**
- Step: `button[i+1].touchArea.x - button[i].touchArea.x` трябва да е constant (= reelStepX ≈ 250px)
- Size: всички `w` и `h` трябва да са еднакви
**Ref values:** x: 108, 358, 608, 858, 1108 → step 250 ✓, all w:224, h:672

## Rule O2: Touch areas — within screen bounds `[C]`

**Обхват:** All buttons with touchArea
**Правило:** Touch areas не трябва да излизат извън екрана.
**Detection:** `x + w > screenWidth || y + h > screenHeight` → flag
**Exception:** Малко overflow (~20px) може да е OK за edge buttons

---

# NORMAL PATTERNS (false positive prevention)

| Pattern | Примери | Защо е OK |
|---------|---------|-----------|
| Overlay с голям scale | GambleRoundOverlayView scale 480x270 | 4x4px pattern → full screen |
| Negative position | GambleRoundView x:-44 | Off-screen animation start |
| Gray color (128,128,128) | `_min` variants | Inactive state styling |
| Dummy elements | BetMenuView dummy_* positions | Layout anchors, не се рендерират |
| Empty elements array | AutoPlayView, LinesView (v/), WinFiguresView (v/) | Populated at runtime from idata |
| Button rssKeys[0] == rssKeys[2] | InfoSwButtonView | enabled == disabled когато няма disabled state |
| Empty rssKey string | StatusLineView status_mid_none | Intentionally invisible |
| Different font sizes per bar | BAR_WIN:77 vs BAR_CREDIT:58 | Win е по-голям by design |

---

# SEVERITY + CATEGORY MATRIX

| Category | Report level | Описание |
|----------|-------------|----------|
| `[I]` Integrity | **error** | Cross-reference failures — почти сигурно бъг |
| `[C]` Consistency | **error** | Self-consistency violations — вероятно бъг |
| `[W]` Convention | **warning** | Convention-based — може да е by design |

| Severity | Trigger | Примери |
|----------|---------|---------|
| **Critical** | Очевидно грешен визуал | Missing rssKey `[I]`(N1), symbol count mismatch `[I]`(I1), green text `[W]`(C1), hidden 18+ `[I]`(A6), crushed fitBox `[C]`(N9), displaced label `[C]`(E4) |
| **High** | Ясно видим при внимание | Knob asymmetry `[C]`(B1), displaced status `[C]`(G1), panel gap `[C]`(A3), wrong alignment `[C]`(B4), rotated panel `[C]`(A7) |
| **Medium** | Видим при сравнение | Semi-transparent bg `[W]`(A1), button misalignment `[C]`(H2) |
| **Low** | Субтилен | Warm tint `[W]`(D1), minor spacing inconsistency |
| **Info** | Потенциален проблем | Missing optional property, uncommon but valid pattern |

**Забележка:** `[W]` findings с severity Critical/High трябва да се преглеждат от потребителя — може да са истински бъг или intentional design choice.
