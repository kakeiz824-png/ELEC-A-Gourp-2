# Git 與 GitHub 新手教學（Shelf Life 專案版）

這份文件是給**第一次用 GitHub 的組員**看的。所有指令都可以直接複製貼上。

本專案的網址是：
<https://github.com/kakeiz824-png/ELEC-A-Gourp-2>

---

## 目錄

1. [先搞懂五個名詞](#1-先搞懂五個名詞)
2. [第一次設定（只做一次）](#2-第一次設定只做一次)
3. [把專案抓下來（clone）](#3-把專案抓下來clone)
4. [把專案跑起來](#4-把專案跑起來)
5. [每天的工作流程（最重要）](#5-每天的工作流程最重要)
6. [完整範例：從改一行字到合併進 main](#6-完整範例從改一行字到合併進-main)
7. [開 Pull Request（網頁操作）](#7-開-pull-request網頁操作)
8. [常見問題排解](#8-常見問題排解)
9. [絕對不要做的事](#9-絕對不要做的事)
10. [指令速查表](#10-指令速查表)
11. [VS Code 圖形介面對照](#11-vs-code-圖形介面對照)

---

## 1. 先搞懂五個名詞

不用背，看過有印象就好，後面都會再用到。

| 名詞 | 白話解釋 |
|---|---|
| **Repository（repo）** | 專案資料夾。分成「**遠端** repo」（放在 GitHub 網站上，大家共用的那份）和「**本地** repo」（你電腦裡的那份）。 |
| **Clone** | 把 GitHub 上的專案**第一次**完整複製到你電腦。**整個專案只做一次**。 |
| **Commit** | 存檔記錄。你改完東西後，打包成一個「進度存檔點」，並寫一句話說明你改了什麼。這時候**還在你電腦裡**，別人看不到。 |
| **Push** | 把你的 commit **上傳**到 GitHub，這樣組員才看得到。 |
| **Pull** | 把 GitHub 上**別人的**新進度**下載**到你電腦。 |
| **Branch（分支）** | 一條獨立的工作線。`main` 是主線（正式版）。你要改東西時，先從 main 拉一條自己的分支去改，改好再合併回 main。這樣就算你寫壞了也不會影響到別人。 |
| **Pull Request（PR）** | 「請求合併」。你在自己的分支改好後，在 GitHub 網頁上發一個 PR，請組員看過、確認沒問題，再合併進 `main`。 |

一句話總結整個流程：

```
GitHub 上的 main
   ↓ clone（第一次）／pull（之後每次）
你電腦裡的 main
   ↓ 開一條新分支
你的分支 → 改檔案 → commit → push
   ↓ 在 GitHub 開 PR
組員 review → 合併回 main
```

---

## 2. 第一次設定（只做一次）

### 2-1. 安裝 Git

**Windows：**

1. 到 <https://git-scm.com/download/win> 下載安裝檔
2. 一路按「Next」用預設值就好，不用改任何選項
3. 裝完後，打開 **PowerShell**（開始選單搜尋 `PowerShell`），輸入：

```bash
git --version
```

有出現類似 `git version 2.55.0.windows.3` 就是成功了。

**Mac：**

打開「終端機」輸入 `git --version`，如果沒裝它會跳出安裝提示，按確定即可。

### 2-2. 安裝 VS Code

到 <https://code.visualstudio.com/> 下載安裝。

### 2-3. 告訴 Git 你是誰

這是為了讓每個 commit 都知道是誰做的。**把下面的名字和信箱換成你自己的**（信箱建議用你註冊 GitHub 的那個）：

```bash
git config --global user.name "你的名字"
```

```bash
git config --global user.email "你的信箱@example.com"
```

設定完檢查一下：

```bash
git config --global --list
```

應該會看到你剛剛填的 `user.name` 和 `user.email`。

### 2-4. 註冊 GitHub 帳號並取得專案權限

1. 到 <https://github.com/> 註冊帳號
2. **把你的 GitHub 帳號名稱給專案擁有者（kakeiz824-png）**
3. 請他到 repo 的 `Settings` → `Collaborators` → `Add people` 把你加進去
4. 你的信箱會收到邀請信，**點信裡的 Accept invitation**

> ⚠️ 沒有做第 4 步的話，你可以下載專案，但**沒辦法 push**，會一直跳權限錯誤。

### 2-5. 登入認證

**GitHub 現在不能用密碼登入了。** 不過你不用先做任何事——第一次執行 `git push` 的時候，Windows 會自動跳出一個瀏覽器視窗要你登入 GitHub，登入完按授權就好，之後就會記住，不用再登入。

---

## 3. 把專案抓下來（clone）

### 3-1. 決定要放在哪

先想好要把專案放在電腦的哪個位置。這裡以 `C:\vsp_program` 為例。

打開 **PowerShell**，建立資料夾並切換進去：

```bash
mkdir C:\vsp_program
```

```bash
cd C:\vsp_program
```

> 💡 如果資料夾已經存在，`mkdir` 會報錯，直接跳過做 `cd` 就好。

### 3-2. 執行 clone

```bash
git clone https://github.com/kakeiz824-png/ELEC-A-Gourp-2.git
```

看到類似這樣就是成功：

```
Cloning into 'ELEC-A-Gourp-2'...
remote: Enumerating objects: 42, done.
Receiving objects: 100% (42/42), done.
```

現在 `C:\vsp_program\ELEC-A-Gourp-2` 就是你的專案資料夾了。

### 3-3. 切換進專案資料夾

```bash
cd C:\vsp_program\ELEC-A-Gourp-2
```

> ⚠️ **從現在開始，所有 git 指令都必須在這個資料夾裡執行。**
> 如果你在別的地方下 git 指令，會看到 `fatal: not a git repository` 的錯誤。
> 隨時可以用 `pwd` 確認自己在哪個資料夾。

### 3-4. 確認一切正常

```bash
git status
```

看到這樣就對了：

```
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

### 3-5. 用 VS Code 打開專案

```bash
code .
```

（最後那個 `.` 是「目前資料夾」的意思，不要漏掉。）

---

## 4. 把專案跑起來

Clone 下來只是拿到程式碼，還要安裝套件才能執行。**這段也只需要做一次。**

確認你在專案資料夾裡（`C:\vsp_program\ELEC-A-Gourp-2`），然後：

### 4-1. 建立虛擬環境

虛擬環境是一個獨立的 Python 套件空間，避免這個專案的套件跟你電腦其他專案打架。

```bash
python -m venv .venv
```

### 4-2. 啟動虛擬環境

```powershell
.venv\Scripts\Activate.ps1
```

成功的話，PowerShell 最前面會多出 `(.venv)` 字樣：

```
(.venv) PS C:\vsp_program\ELEC-A-Gourp-2>
```

> ⚠️ **每次重開 PowerShell 都要重新執行這一行。** 沒有 `(.venv)` 就代表沒啟動。
>
> 如果跳出「因為這個系統上已停用指令碼執行」的紅字錯誤，先執行下面這行再重試：
>
> ```powershell
> Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
> ```

**Mac 使用者**用這行代替：

```bash
source .venv/bin/activate
```

### 4-3. 安裝套件

```bash
python -m pip install -r requirements.txt
```

### 4-4. 跑測試，確認環境沒問題

```bash
python -m pytest
```

應該看到 `38 passed`。有看到就代表你的環境完全正常。

### 4-5. 啟動網站

```bash
python -m uvicorn app.main:app --reload
```

然後打開瀏覽器輸入 <http://127.0.0.1:8000>，就會看到 Shelf Life 的三個書架畫面。

要**停止伺服器**，回到 PowerShell 按 `Ctrl + C`。

---

## 5. 每天的工作流程（最重要）

**每次要開始寫東西，都照這六步走。**

### 步驟 1：先切回 main，並更新到最新版

```bash
git switch main
```

```bash
git pull
```

> 💡 **為什麼要先 pull？** 因為組員可能在你睡覺時改了東西。如果你不先更新就開始寫，等一下就會發生「衝突」，處理起來很麻煩。
> **養成習慣：開始寫程式前，先 pull。**

### 步驟 2：開一條自己的新分支

```bash
git switch -c feature/你要做的事
```

分支名稱用**英文小寫**，用 `-` 連接，並且要看得出來你在做什麼。例如：

```bash
git switch -c feature/add-book-search
```

```bash
git switch -c fix/rating-validation
```

命名慣例：
- `feature/xxx` — 新增功能
- `fix/xxx` — 修 bug
- `docs/xxx` — 只改文件

> 💡 `-c` 是 create 的意思。**分支只需要建立一次**，之後要切回去用 `git switch 分支名稱`（不用 `-c`）。

### 步驟 3：改你的檔案

用 VS Code 正常寫程式、存檔就好。這一步跟 Git 無關。

改完後**務必跑一次測試**，確認你沒把東西弄壞：

```bash
python -m pytest
```

### 步驟 4：看看自己改了什麼

```bash
git status
```

紅色的檔案 = 你有改動但還沒準備提交的。

想看具體改了哪幾行：

```bash
git diff
```

（按 `Q` 離開檢視畫面。）

### 步驟 5：Commit（存檔）

先把要提交的檔案加進來：

```bash
git add .
```

> 💡 `.` 代表「這個資料夾裡所有改動的檔案」。
> 如果只想提交特定檔案，就寫檔名，例如 `git add app/lookup.py`。

然後寫一句話說明你改了什麼：

```bash
git commit -m "Add search box to the reading shelf"
```

**Commit 訊息怎麼寫：**

| ✅ 好 | ❌ 不好 |
|---|---|
| `Add rating filter to the stats endpoint` | `update` |
| `Fix crash when the book title is empty` | `修好了` |
| `Update README with setup steps` | `aaa` |

原則：用**動詞開頭**，講清楚**做了什麼**，讓組員三個月後看得懂。專案裡目前是用英文，跟著用英文即可。

### 步驟 6：Push 到 GitHub

**第一次** push 這條新分支時，要用這行（多了 `-u origin 分支名`）：

```bash
git push -u origin feature/add-book-search
```

**同一條分支之後的每一次** push，只要打：

```bash
git push
```

Push 成功後，畫面上會出現一個網址，**點它就可以直接去開 PR**（見下一節）。

---

## 6. 完整範例：從改一行字到合併進 main

假設你要修改 README 裡的一句話，從頭到尾是這樣：

```bash
cd C:\vsp_program\ELEC-A-Gourp-2
```

```bash
git switch main
```

```bash
git pull
```

```bash
git switch -c docs/fix-readme-typo
```

接著用 VS Code 打開 `README.md`，改好、存檔。回到 PowerShell：

```bash
git status
```

會看到：

```
On branch docs/fix-readme-typo
Changes not staged for commit:
        modified:   README.md
```

繼續：

```bash
git add .
```

```bash
git commit -m "Fix typo in the README setup section"
```

```bash
git push -u origin docs/fix-readme-typo
```

然後到 GitHub 網頁開 PR（下一節），組員按合併，就完成了。

**合併完成之後**，記得把你電腦切回 main 並更新：

```bash
git switch main
```

```bash
git pull
```

這時候你的 main 就包含剛剛的修改了。下次要做新的事情，再從步驟 1 重來一次。

---

## 7. 開 Pull Request（網頁操作）

1. 打開 <https://github.com/kakeiz824-png/ELEC-A-Gourp-2>
2. 頁面上方通常會出現一條黃色橫幅：
   `docs/fix-readme-typo had recent pushes` — 右邊有綠色按鈕 **Compare & pull request**，點它
   （如果沒看到，就點上方的 **Pull requests** 分頁 → **New pull request**，然後在 `compare:` 下拉選單選你的分支）
3. 確認上方顯示的方向是：
   `base: main` ← `compare: 你的分支名稱`
   **方向不要反了。**
4. **Title**：寫這次改動的重點（可以直接用你的 commit 訊息）
5. **描述欄**：寫清楚三件事
   - 我改了什麼
   - 為什麼要改
   - 怎麼確認它有效（例如「跑過 `python -m pytest`，38 個測試全過」）
6. 右側 **Reviewers** 選一位組員
7. 按綠色的 **Create pull request**
8. 等組員 review。組員如果留言要你修改，你就在**同一條分支**上繼續改 → `git add .` → `git commit -m "..."` → `git push`，PR 會自動更新，不用重開一個
9. Review 通過後，按 **Merge pull request** → **Confirm merge**
10. 合併完可以按 **Delete branch** 把用完的分支刪掉（GitHub 上的），保持乾淨

---

## 8. 常見問題排解

### Q1：`fatal: not a git repository`

**原因：** 你不在專案資料夾裡。

**解法：**

```bash
cd C:\vsp_program\ELEC-A-Gourp-2
```

### Q2：push 被拒絕，出現 `rejected` 或 `non-fast-forward`

```
! [rejected]  main -> main (fetch first)
```

**原因：** 組員在你之後推了新東西，GitHub 上的版本比你新。

**解法：** 先拉下來再推：

```bash
git pull
```

```bash
git push
```

如果 `git pull` 之後出現衝突，看 Q3。

### Q3：發生衝突（CONFLICT）

```
CONFLICT (content): Merge conflict in app/lookup.py
Automatic merge failed; fix conflicts and then commit the result.
```

**原因：** 你和組員改到**同一個檔案的同一行**，Git 不知道該聽誰的。

**解法：**

1. 用 VS Code 打開有衝突的檔案，你會看到：

```
<<<<<<< HEAD
你寫的版本
=======
組員寫的版本
>>>>>>> main
```

2. VS Code 會在這段上面顯示藍色小字選項：
   - **Accept Current Change** — 留你的
   - **Accept Incoming Change** — 留組員的
   - **Accept Both Changes** — 兩個都留

   點一個，或是直接手動編輯成你要的樣子。

3. **把 `<<<<<<<`、`=======`、`>>>>>>>` 這三行符號全部刪掉**，只留下正確的程式碼

4. 每個衝突的檔案都處理完後：

```bash
git add .
```

```bash
git commit -m "Resolve merge conflict in lookup"
```

```bash
git push
```

> 💡 **不確定該留哪個版本時，先問組員再改，不要自己猜。**

### Q4：不小心在 main 上改了東西，還沒 commit

**解法：** 把改動帶到新分支去：

```bash
git switch -c feature/我要做的事
```

改動會跟著你過去，然後正常 `git add` / `git commit` 就好。

### Q5：commit 訊息打錯字，還沒 push

```bash
git commit --amend -m "正確的訊息"
```

> ⚠️ **已經 push 出去的 commit 不要用 `--amend`**，會害組員的版本對不上。

### Q6：改壞了，想把某個檔案還原成最後一次 commit 的樣子

```bash
git restore 檔案名稱
```

> ⚠️ **這會直接丟掉你的修改，救不回來。** 執行前先確定你真的不要了。

### Q7：`.venv` 或 `shelf_life.db` 出現在 `git status` 裡

正常情況下不會，因為 `.gitignore` 已經擋掉了。如果真的出現，**不要 commit 它們** — 虛擬環境有幾百 MB，資料庫是你本機的測試資料，推上去會造成大麻煩。回報給組長處理。

### Q8：`LF will be replaced by CRLF` 警告

這是 Windows 和 Mac 換行符號不同造成的**警告，不是錯誤**，可以直接忽略，不影響任何功能。

### Q9：忘記自己在哪條分支上

```bash
git branch
```

前面有 `*` 的那條就是你現在所在的分支。

### Q10：想看專案的歷史紀錄

```bash
git log --oneline -10
```

顯示最近 10 筆 commit。按 `Q` 離開。

---

## 9. 絕對不要做的事

| ❌ 不要 | 原因 |
|---|---|
| **直接在 `main` 分支上改東西然後 push** | 沒人 review，寫壞了整組都跑不動 |
| **push 前不跑 `python -m pytest`** | 你會把壞掉的程式推給全組 |
| **commit `.venv` 資料夾** | 幾百 MB，而且每台電腦的內容都不一樣 |
| **commit `.env` 檔或任何密碼、金鑰** | 推上去就等於公開了，而且刪掉也還留在歷史紀錄裡 |
| **用 `git push --force`** | 會**覆蓋掉**組員的進度，且救不回來 |
| **一個 commit 改 20 個檔案** | 出事的時候沒人知道是哪一行造成的 |
| **commit 訊息寫 `update`、`123`、`修改`** | 三天後你自己也看不懂 |
| **遇到看不懂的錯誤就一直亂試指令** | 先截圖問組員，比亂試安全 |

---

## 10. 指令速查表

**每天最常用的（背這七個就夠了）：**

```bash
git status          # 我現在什麼狀態？（不確定時就打這個）
git pull            # 下載組員的最新進度
git switch -c 名稱   # 開一條新分支
git add .           # 把改動加入準備區
git commit -m "訊息" # 存檔
git push            # 上傳到 GitHub
git log --oneline   # 看歷史紀錄
```

**分支相關：**

| 指令 | 用途 |
|---|---|
| `git branch` | 列出所有本地分支，`*` 是目前所在 |
| `git switch main` | 切換到 main 分支 |
| `git switch -c feature/xxx` | 建立並切換到新分支 |
| `git branch -d feature/xxx` | 刪除本地已合併的分支 |

**查看改動：**

| 指令 | 用途 |
|---|---|
| `git status` | 哪些檔案改了 |
| `git diff` | 具體改了哪幾行（尚未 `git add` 的） |
| `git diff --staged` | 已經 `git add` 的改動內容 |
| `git log --oneline -10` | 最近 10 筆 commit |

**專案執行：**

| 指令 | 用途 |
|---|---|
| `.venv\Scripts\Activate.ps1` | 啟動虛擬環境（每次開新視窗都要） |
| `python -m pytest` | 跑測試 |
| `python -m uvicorn app.main:app --reload` | 啟動網站 |

> 💡 `git checkout` 是 `git switch` 的舊寫法，功能一樣。你在網路上查到的舊教學可能會用 `git checkout -b`，那等同於 `git switch -c`。

---

## 11. VS Code 圖形介面對照

不想打指令的話，VS Code 左側有一個**分支圖示**的按鈕（Source Control，快捷鍵 `Ctrl + Shift + G`），可以用點的完成大部分操作：

| 你想做的事 | 指令 | VS Code 操作 |
|---|---|---|
| 看改了什麼 | `git status` | 點左側 Source Control 圖示，檔案列在 Changes 底下 |
| 加入準備區 | `git add .` | 滑鼠移到檔案上，點右邊的 **+** |
| Commit | `git commit -m "..."` | 上方輸入框打訊息，按 **✓ Commit** |
| Push | `git push` | 按 **Sync Changes**，或右上 `...` → **Push** |
| Pull | `git pull` | 右上 `...` → **Pull** |
| 切換分支 | `git switch main` | 點**左下角**顯示的分支名稱，選要切的分支 |
| 開新分支 | `git switch -c xxx` | 點左下角分支名稱 → **Create new branch** |

> 💡 建議一開始還是用指令，因為出問題時網路上查到的解法幾乎都是指令。等熟悉流程了再用圖形介面加速。

---

## 遇到問題怎麼辦

1. **先執行 `git status`** — 它通常會直接告訴你現在是什麼狀況、下一步該做什麼
2. **把完整的錯誤訊息截圖**貼到群組問，不要只說「我壞掉了」
3. **不確定的指令不要亂執行**，特別是含有 `--force`、`reset --hard`、`clean` 的
4. 你的程式碼只要 commit 過就幾乎不可能真的弄丟，**冷靜問人就好**
