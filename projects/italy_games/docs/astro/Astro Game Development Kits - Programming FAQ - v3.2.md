Astro

# Astro Game Development Kits
# Programming FAQ

For AstroGDK version 3.2
For Italian VLT (Comma 6b) and Morocco VLT

S/N: SYSDEV-AGDK-002

Copyright © 2017 to 2022 Astro Corp. All Rights Reserved.

Astro

THE INFORMATION IN THIS DOCUMENT IS CONFIDENTIAL, IT MAY NOT BE REPRODUCED, STORED, COPIED OR OTHERWISE RETRIEVED AND/OR RECORDED IN ANY FORM IN WHOLE, OR IN PART, NOR MAY ANY OF THE INFORMATION CONTAINED THEREIN BE DISCLOSED.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2

# Revision History

<table>
  <tbody>
    <tr>
        <td>Revision</td>
        <td>Date (Y/M/D)</td>
        <td>Comments</td>
    </tr>
    <tr>
        <th>1 of 1.6</th>
        <th>2018/12/11</th>
        <th>Separate from Programming Guide document.</th>
    </tr>
    <tr>
        <td>2.0</td>
        <td>2019/2/2</td>
        <td>For AstroGDK 2.0, add two FAQ’s.</td>
    </tr>
    <tr>
        <td>2.1</td>
        <td>2019/5/20</td>
        <td>Add FAQ’s for AtroGDK 2.1.</td>
    </tr>
    <tr>
        <td>2.6</td>
        <td>2019/10/1</td>
        <td>Add FAQ’s for AtroGDK 2.6</td>
    </tr>
    <tr>
        <td>2.6</td>
        <td>2019/10/1</td>
        <td>Add FAQ’s for AtroGDK 2.6</td>
    </tr>
    <tr>
        <td>2.7</td>
        <td>2020/10/1</td>
        <td>Add FAQ’s for AtroGDK 2.7</td>
    </tr>
    <tr>
        <td>2.9</td>
        <td>2021/7/23</td>
        <td>Add FAQ’s for AtroGDK 2.9</td>
    </tr>
    <tr>
        <td>2.9.1-3.2</td>
        <td>2022/7/15</td>
        <td>(No change)</td>
    </tr>
  </tbody>
</table>

# Contents

Revision History ..................................................................................................................................... 2
Contents ................................................................................................................................................. 2
FAQ ......................................................................................................................................................... 3

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 2
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

# FAQ

### Q1: Can simulate buttons?
A1: Yes. Through keyboard, may simulate physical buttons and some device events. Please refer to Section 4.4.1 of programming guide for detail.

### Q2: How to control the sound volume?
A2: The sound strength in sound materials must be considered. Also Astro VLT uses an external volume control knob to control volume globally on the VLT. Please refer to Section 3.7 of programming guide for detail.

### Q3: Can we simulate Bill Acceptor (Note reader).
A3: Yes. By pressing key `<5>` and `<6>` on the keyboard at the same time to simulate inserting an amount, e.g. 100 euro, banknote. Please refer to Section 4.4.1 and 4.4.3 of programming guide for detail.

### Q4: Can we simulate Ticket printer?
A4: No. While requesting cash-out (TICKET OUT) by pressing key `<1>`, the current credits just reset to zero (NULL ticket printer) in development environment.

### Q5: Can we simulate Door switch?
A5: Yes. By pressing and releasing `<F3>` to simulate main door opened and closed; by pressing and releasing `<F4>` to simulate logic unit door opened and closed. Please refer to Section 4.4.1 of programming guide.

### Q6: Do we need to make the Game working in Windows and Linux, or we can develop and use only Linux?
A6: You can develop and use only Linux. Windows can be totally NOT necessary. Many game teams like to develop game in Windows first just because they are familiar with coding and debugging

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 3
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

in Window environment. Also, sometimes it's easy to make a prototyping, and sometimes for demo purpose, etc. That's why we also provide the Windows support.

### Q7: Suggested Development Environment.
A7: For performance issue, Visual C/C++ (for Windows), and gcc/g++ (for Linux), are most used in our company, Astro Corp. In practice, game teams may develop games with their favorite development environments and languages, e.g. Python, C#, Java, etc. in case of it can link with 32-bit shared object "libak2api.so".

### Q8: About touch panel, is it possible to use general touch not 3M? Can you integrate our general touch to framework?
A8: (updated 2019/1/22) From Astro game system 2.0, all touch panel signals are transformed to mouse pointer signals. So a game program is also appreciated to just read information of mouse pointer from operating system instead of messages "ac_touch_pressed" and "ac_touch_released". So a developer may use any brand of touch panel in case of this touch panel is able to simulate and return signal of mouse pointer. Please refer to Section 2.7 for detail.

### Q9: How about security patches?
A9: VLT is an embedded environment. Not opened and used for general purposes. The firewall, VPN, encrypted and hashed data, and process monitoring, are constructed to protect the environment. Even there are some security issues in some inner software, will not affect the security of total.
(updated 2019/1/22) From Astro game system 2.0, operation system and kernel of VLT is upgraded to new version.

### Q10: The gcc 4.4.6 version is very old, can we add devtoolset-6 package to make it possible using the new gcc 6.3.1 features?
**(Note: This package will be necessary when developing the games and on submission for certification?)**
A10: The document says you can use wide range of program languages as long as which can access the "AK2API". So of course the gcc version 6 or later is OK. You can just install your favorite

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 4
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

development environment into the Linux box, e.g. the new-version gcc, the java compiler, anything else.

But note, if the "runtime" of game requires some must-have libraries or packages which are not pre-installed in the embedded environment of VLT, you must have those libraries together with your submission, or talk about the runtime environment with the AstroGDK team of Astro Corp., so consider modifying the embedded OS to have them.

(updated 2019/1/22) From Astro game system 2.0, gcc 4.8 and gcc 7.3 were pre-installed in development environment. Gcc 4.8 supports C++11 and few C++14 standards with parameter `-std=c++1y`. Gcc 7.3 supports full C++17 standards with parameter `-std=c++1z`.

### Q11: The game lobby, select game there, can we use our design / layout?
A11: Limited Yes.
(1) Edit the file "Layout.sisal.xml" in Game lobby to modify the icon positions, background pictures, etc.
(2) Acquire AstroGDK for Game lobby to make your own Game lobby.

### Q12: Is there any limit on the size of game package, movies etc?
A12: In software's point of view, no.
May be limited by the storage size and requirement of loading time.
Sizes of games made by Astro Corp., in average, are about 100 ~ 300 MBytes.

### Q13: Is there any limits concerning the RNG server, size of RNG numbers, call frequency etc.?
A13: A single RNG request can request one or up to 63 random numbers at the same time. Every RNG request is put into a queue structure beforehand. So you can raise multiple RNG requests within a short time without problem. Each random number returned is an unsigned integer and always in range of 0 to 2<sup>31</sup>-1 (0 ~ 2147483647).

### Q14: Is it possible to install GDK and develop game only on Linux machine?
A14: Yes. Windows machine is not necessary.

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 5
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

### Q15: How long does it take the message “ca_game_snapshot” or call ak2api_nvbuf_if_synced()?
A15: **“ca_game_snapshot”** is run in blocking manner. It will not return until the AstroKernel has taken snapshot of the screen. Please refer to ak2api.h and in the first paragraph of page 44 of section 3.2.3. It takes about 100 milliseconds in Astro VLT in practice.
**ak2api_nvbuf_if_synced()** is run in non-blocking manner. It just checks the commit state of NVRAM. Please refer to “ak2api.h” and bottom of Section 3.2.6 of programming guide for detail.

### Q16: Is it possible to control some devices to produce special effects to player by ourselves without sending specific atmosphere id message?
A16: Now, no.

### Q17: We want to use ours framelight, do you have free RS232 port for this?
A17: Yes. There are four external COM ports, and AstroKernel uses up to three. Refer to section 2.1.2 of programming guide, and the COM4 is free and you may use it.
If your game uses any of system resource not defined in this document, like COM port, USB, etc., please let us know beforehand and mention it in the technical part of your game document.

### Q18: Do you have documentation on recovery - how the kernel behaves and what is expected from the games?
A18: Yes, please refer to Section 3.3 of programming guide for detail.

### Q19: Have you considered recovery of endless loop?
A19: Yes. If some problems led to a game in state of endless loop, blocking forever, or error always happened in every-time launching. The operator can instruct the VLT to do a system recovery through management web or POS, we call it “force detach”, and later this terminal will be reset to an initial state.

(New from version 1.6.1 below)

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 6
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

**Q20: About Log. Document says log saved to "AstroKernel\Runtime\data\ask.log" Does it works under WIN BOX?**
A20: Yes. This file is created by Runtime/start.sh or Runtime\start.bat. You may look into the script file for a clear view.

**Q21: About Outcome Detail. Inside example formatting of the Outcome Details to notify to AstroKernel there are references to the field:**
**VSTK:\<amount\>: the virtual/displayed bet amount (no accounting changed);**
**What do you mean? Could you explain to us?**
A21: For examples, free game and ultra spin, the bet amount is displayed but not really subtracted from current credits or energy point, should be output to VSTK:\<amount\> for just reference. In back office, will only accumulate all "STK" amount to audit the real bet amount of a game match regardless of "VSTK".

**Q22: AstroKernel (ask) launches game program "app" as its child process. Can "app" launch other child processes, and the main loop and UI-updating is possible to be located in child or even grandchild process?**
A22: Yes. AstroKernel just launches "app" and then wait there until "app" quit, and then gets exit code of "app" process. AstroGDK doesn't care how your game software runs, one or multiple processes / threads are all OK.

**Q23: SDL / SDL2 are widely used in many graphics software. Could you build-in the libraries of them into VLT OS?**
A23: Yes. The up-to-date VLT embedded and Linux development machine have built-in SDL and SDL2 (SDL2_gfx, SDL2_image, SDL2_mixer, SDL2_net, SDL2_ttf). We provide the disk image of Linux development machine for game teams to upgrade.

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 7
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

### Q24: About MAX WIN. If the win is 5000,00 Euro (Win max). What does GDK wait by us? The payout command “ca_credit_payout” sent by us or the GDK proceedes to the payout and it send us a suspend command “ ac_flow_suspend” ?

A24: AstroKernel does not care of win amount of game. In case of win amount equal or exceeding 5000,00 Euro (C6b Regulation), game program must be aware of it and request payout by itself by sending message “ca_credit_payout”. When AstroKernel receives it, will send “ac_flow_suspend” immediately, then do the payout (print ticket), and eventually send “ac_flow_resume”.

For Regulation C6b, a game match is not allowed to win over 5000,00 Euro. For example, a game can design its odds table to be impossible to win over 5000; Or when exceeding 5000 before reaching the end of the game match, just interrupt the game match and just award 5000. About the later, please confirm with your certificate lab.

### Q25: About GAME GUI: Do you have an example where the updated GUI is build to the format .exe as indicated in documentation?

A25: AstroKernel just raises "app" as a child process, and then "app" or its derived process(es) displays graphics/audio totally in its own manner.

Sometimes AstroKernel would show its UI (pop-up dialog box, a top-most window) upon game display, e.g. a dialog box showed in case of door opened, responsible game setting has reached the limit, etc. The manner of opening/closing pop-up dialog box is totally transparent to game software.

There are libraries OpenGL, SDL, SDL2, jpeg, Xvid, etc. available in VLT embedded and Linux box (Linux development machine), for your graphics engine to use.

### Q26: Are ak2api already installed in linux box image? If yes, where?

A26: No, ak2api (headers/libraries) is in AstroGDK package independent of Linux box image. You may copy AstroGDK into Linux box directly, or just access/mount to AstroGDK directory/folder by network file system (NFS/CIFS).

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 8
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

**Q27: Our game runs fine as active mode, but we have been unable to start the AstroKernel 1.6.1 on the Linux box running the start.sh. The process quits very soon. I've attached the relevant log. Why?**
A27: please confirm the file "AstroKernel/GameLobby/app" which must have executable 'x' attribute. If not, configure it to executable by below command:
`# chmod +x AstroKernel/GameLobby/app`

(New from AstroGDK version 2.0 below)

**Q28: Can Bias (non-uniform) random number distribution accepted by Italian certification? For example, requiring to scale original random number to [0..86], how?**
A28: No. Italian certification requires strict uniform distribution of random numbers used. Game program must always carry out modulus operation on original random number by power-of-2 value. One method to handle custom non-power-of-2 range, for example [0..86], is carrying out modulus operation by 128, if the result value is greater than 86, deny it, fetch a new random number, and carry out modulus operation on it again, so on, until result value is in range of [0..86].

**Q29: Regarding rng timeout handling, if I choose to return 11 on timeout the AstroKernel will always rollback the game no matter how many points the player has won? Isn't it too hard for a player to lose the whole game win?**
A29: No. Game program cannot exit with 11 in any cases of RNG timeout. Only the first rng request of a game cycle (for the main / base game) timed out can exit with 11. AstroKernel only returned "the last" bet amount to player. Any won already happened will always be kept.

(New from AstroGDK version 2.1 below)

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 9
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

**Q30: Should a game provides its media file “04:Bouncing Icon – Label”, or draw label into bouncing images?**

The image shows a game lobby interface for "Sisal" with various game icons. Annotations point to different UI elements:
- **02:GAME ICON-ANIMATION**: Points to the main animated game icon for "SAPA INCA".
- **04:BOUNCING ICON-LABEL**: Points to a green "ESCLUSIVO" label overlaid on a game icon.
- **03:BOUNCING ICON-ANIMATION**: Points to the animated background of a bouncing icon.
- **05:BOUNCING ICON-IMAGE**: Points to the static image within a bouncing icon for "ATLANTIS".
- The bottom bar shows "IMPOSTA LIMITI", "CREDITO € 5.000,00", and "TICKET OUT".
- Top navigation tabs include: I PIÙ GIOCATI, ESCLUSIVA, NOVITÀ, ASTRO, SISAL, SCEGLI TU.

A30: No. Several “04:Bouncing Icon – Label” .PNG files provided by Astro system are independent with bouncing images. The certain label will be drawn upon bouncing image in Game lobby dynamically depending on configuration of game lobby by operator.

(New from AstroGDK version 2.6 below)

**Q31: Is there any limit to the number of game recoveries? Any way to test this?**
A31: No limit now. Will support in the future.

**Q32: We use an acceptance rejection method for scaling random numbers. When we call `ca_game_step` do we need to log every random number used in the phase (even rejected ones) or only the scaled (final) ones?**
A32: The main principle is, if feeding those logged random numbers again, will have the same outcome. So just log those used random numbers with their original values.

(New from AstroGDK version 2.7 below)

**Q33: MONEY-based game vs. CREDIT-based (not money) game?**
A33: MONEY-based game means displaying current credits, bet amount, won amount, etc. in money (e.g. 1.234,50 Euro) directly. CREDIT-based game means displaying current credits, bet

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 10
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.

Astro Game Development Kits - Programming FAQ
AstroGDK version 3.2
Astro

amount, won amount, etc. in units of credits (e.g. 12.345, if 1 credit=10 eurocent), so a conversion between money and credits will be performed. Use configuration item "accounting"/"AU" to determine game should be in which type. If it's 0, game should be MONEY-based. If it's not 0, game should be CREDIT-based and use the value to convert between money and credits. E.g. value is 10, it means 1 credits = 10 Eurocents.

(New from AstroGDK version 2.9 below)

### Q34: May game program store its private files and/or use another mechanism to implement NVRAM, e.g. sqlite?
A34: Yes, game program may access its private directory allocated by querying configuration item "custom"/"pz_path". It's located on permanent file system of SSD.

### Q35: May I support game programming in Node.js or HTML5.
A35: Yes, related runtime files must be prepared by game team and put together with game release package.

Copyright © 2017 to 2022 By Astro Corp. All Rights Reserved. Page 11
The information in this document is confidential, it may not be reproduced, stored, copied or otherwise retrieved and/or recorded in any form in whole, or in part, nor may any of the information contained therein be disclosed.