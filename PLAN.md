# Project Plan

撰寫於 2026-08-06。涵蓋我們自己找到的錯誤處理問題、Emma Zhou 的 code review 留言,
以及用作者名找書。

工作量:**S** 約半小時內、**M** 約半天、**L** 一天以上。

每一條都對**目前的工作樹**驗證過,不是照抄 review 文字 —— review 是針對已 commit
的版本寫的,而 `mcp_server/server.py` 等檔案之後改過。凡是 review 的判斷與實測不符,
更正與證據都記錄在後面的細節章節。那些情況下該修的還是要修,只有「為什麼修」變了。

## 開始前必讀:工作樹狀態

作者搜尋與分頁**已經實作完成但尚未 commit**。`git status` 顯示 20 個修改檔案加 1 個
新測試檔,`origin/main` 不含這些變更。

兩個影響:

1. Emma review 引用的行號、以及我們自己找到的 error handling 行號(171/179/186/207)
   **都已經位移**。細節章節同時列出兩組行號。
2. 順序 3 不是開發工作,是「把已完成的東西送出去」。

在順序 3 完成前不要開始其他項目,否則會重複修改同一批檔案。

## Must Have

| 順序 | 工作項目 | 工作量 | 相依項目 | 狀態 |
|---|---|---|---|---|
| 1 | 確認專案可以正常啟動並通過完整測試 | S | 無 | 已完成 |
| 2 | 在瀏覽器實際操作 Title/Author 切換與分頁按鈕 | S | 1 | 未完成 |
| 3 | Commit 並 push 作者搜尋與分頁 | S | 2 | 未完成 |
| 4 | 修好書卡四個 listener 的錯誤處理(細節一) | M | 3 | 未完成 |
| 5 | MCP 工具補上一般例外處理(細節四) | S | 3 | 未完成 |
| 6 | MCP 搜尋輸入正規化(細節三) | S | 3 | 未完成 |
| 7 | 用 MCP Inspector 測試三個 Tool 並記錄證據 | M | 5、6 | 未完成 |
| 8 | 確認 Render 部署版本可以正常運作 | S | 3、4 | 未完成 |

順序 1 已完成的依據:`.venv` 建好、`pytest` 159 passed、semgrep 255 條規則 0 findings、
uvicorn 實際啟動並對真實 Open Library 驗證過搜尋與加入流程。

順序 4、5、6 之間沒有相依,可以分給不同人並行。

## Should Have

| 工作項目 | 工作量 | 狀態 |
|---|---|---|
| `_format_book` 與 `_book_payload` 的欄位定義去重(細節五) | S | 未完成 |
| 回覆 Emma 關於 `seed/books.json` 加 id 的留言(細節六) | S | 未完成 |
| 把「按 work 分組版本」寫進 `DESIGN.md` 未來工作 | S | 未完成 |
| 清掉 `README.md` 的過期敘述(仍寫著 MCP server 尚未完成) | S | 未完成 |

## Could Have

| 工作項目 | 工作量 | 狀態 |
|---|---|---|
| 導入 JavaScript 測試工具,讓細節一能自動化驗證 | L | 未完成 |
| 按 Open Library work key 分組版本,消除重複的譯本與套書 | L | 未完成 |
| 快取 Open Library 回應,減少重複查詢 | M | 未完成 |
| 分頁改成可點選的頁碼,而非只有 Previous / Next | S | 未完成 |

## Won't Have

- 複雜的使用者登入系統。
- 非必要的額外 API。
- **在 `seed/books.json` 加 id 欄位。** 已確認不適用於這個檔案,理由見細節六。
- 需要兩小時以上、但不是 Must Have 的功能。

## Work Order

1. 確認專案能啟動 —— 已完成。
2. 在瀏覽器點過切換選單與分頁,補完被中斷的驗證。
3. Commit 並 push 作者搜尋與分頁。部署來源是 `main`,`main` 一動 Render 就會重新部署。
4. 修好書卡的錯誤處理 —— 這批裡唯一真正的 bug,而且使用者看得見。
5. 加入 MCP 一般例外處理 —— 很小,而且讓後續工作更好除錯。
6. 加入 MCP 輸入正規化。
7. 用 MCP Client 完整測試三個 Tool。
8. 確認部署版本正常。**測試前務必 Ctrl+Shift+R**:HTML 結構變了,快取的舊 `app.js`
   不只是行為不同,是會直接壞掉。
9. 更新文件 —— `DESIGN.md` 的 Inspector 證據、Should Have 裡的文件項目。

## Review 判斷總結

| 項目 | Review 嚴重度 | 我們的判斷 | 修不修 |
|---|---|---|---|
| 書卡 listener 錯誤處理(我們自己找的) | — | 真的 bug | 修 |
| MCP 輸入正規化 | critical | 缺漏是真的,但沒有請求完整性風險 | 修,降級 |
| MCP 一般例外處理 | suggestion | 缺漏是真的;但所述成因與「server 會掛」都不成立 | 修,理由不同 |
| `_format_book` 重複 | nitpick | 同意,但不加換行常數 | 部分修 |
| `seed/books.json` 加 id | nitpick | 不適用於這個檔案 | 不修,改為回覆留言 |

---

# 項目細節

## 細節一:書卡四個 listener 缺少錯誤處理

我們自己找到的。這是清單裡唯一真正的缺陷。對應 Must Have 順序 4。

### 問題

`static/app.js` 的 `buildCard` 裡有四個 listener 發出 API 請求卻不處理失敗:

| 動作 | 已 commit 版本行號 | 目前工作樹行號 |
|---|---|---|
| 把書移到另一個書架 | 171 | 192 |
| 重試 metadata 查詢 | 179 | 200 |
| 刪除書 | 186 | 207 |
| 儲存評分與評論 | 207 | 228 |

### 證據

`api()` 的設計就是非 2xx 一律丟例外:

```js
// static/app.js:42
if (!response.ok) {
  ...
  throw error;
}
```

四個 listener 都沒有 `try`/`catch`,所以請求失敗會讓 listener 的 promise 變成
rejected,`await api(...)` 之後的每一行都被跳過。三個後果都成立:

- **載入訊息卡在畫面上。** 重試按鈕在呼叫前設定 `Looking up "…"`,呼叫後才清掉。
  失敗時清除那行(`static/app.js:203`)不會執行,那條訊息就一直留著。
- **使用者什麼都不知道。** 錯誤只以 unhandled promise rejection 出現在 console。
- **改動看起來成功了,其實沒存。** 換書架最嚴重:下拉選單的新值是**瀏覽器自己重繪的**,
  而負責「向伺服器問真實狀態並照實重畫」的是 `static/app.js:197` 的 `refresh()`。
  它被跳過,卡片就顯示著資料庫從沒儲存過的書架。

### 做法

1. 在 `api()` 旁邊加一個小 helper,包住一個動作:失敗時用
   `setHint(..., "error")` 回報,**無論成功或失敗都重新渲染**,讓卡片不可能保留
   樂觀狀態。

   ```js
   /** 執行一個卡片動作,失敗時回報,並且無論如何都重新同步。 */
   async function cardAction(work, failureMessage) {
     try {
       await work();
     } catch (error) {
       setHint(error.message || failureMessage, "error");
     } finally {
       await refresh();
     }
   }
   ```

   `refresh()` 放在 `finally` 是修好第三個症狀的關鍵:寫入失敗時下拉選單會彈回
   已儲存的值。

2. 四個 listener 都改走這個 helper,各自帶一句指名動作的訊息,讓「無法移動這本書」
   和「無法儲存評論」能區分。

3. 依照原始 finding 的要求,把同樣做法套用到其他發 API 請求的 listener。清查結果:
   - `retryButton`(200)、`reviewForm` submit(228)、`moveSelect` change(192)、
     刪除按鈕(207) —— **要修**,即上表四項。
   - `buildSearchResult` 的 `chooseButton` —— **已經處理**,有
     `try`/`catch`/`finally` 並會恢復按鈕。這就是要照抄的範本。
   - `addForm` submit 與分頁按鈕 —— **已經處理**,走 `runSearch`,有
     `try`/`catch`/`finally`。
   - 封面圖的 `error` listener —— 沒有 API 呼叫,只換佔位圖。不用改。
   - `reviewButton`(221) —— 只切換表單顯示,沒有 API 呼叫。

   所以上表四項就是完整清單。

4. 如果 `refresh()` 自己失敗,`cardAction` 會從 `finally` 往外丟例外。要加保護,
   否則這個修法會在斷網時把它剛移除的 bug 帶回來。

### 檔案

`static/app.js`。

### 測試

專案沒有 JavaScript 測試,也沒有 JS test runner,導入一個比這個修法本身更大,
屬於 Could Have。手動驗證:

1. 停掉 API,然後操作四個控制項。每一個都必須在 hint 顯示錯誤,而且書架下拉選單
   必須彈回已儲存的值。
2. 重啟 API,確認四個功能都正常。

做完把結果記錄在這個檔案。**沒有實際跑過就不要聲稱通過。**

### 完成條件

四個 listener 都會回報失敗,任何控制項都不可能顯示伺服器未確認的狀態,而且上面的
手動檢查已經跑過並記錄。

## 細節二:用作者名找書

對應 Must Have 順序 2、3。

### 狀態

已在工作樹實作完成,已對真實 Open Library 驗證,**尚未 commit**。

- 透過 `app/openlibrary.py` 的 `search_author` 查 Open Library 的 `author=` 索引,
  以 `search_by_author` MCP tool 對外提供,經 `lookup` 邊界進入應用程式,
  seed fallback 保留。
- 搜尋框旁的 Title/Author 選單告訴伺服器要查哪個索引。先前兩次「從查詢字串自動推斷」
  都失敗了,見 `DESIGN.md` 7.6。
- 結果分頁,每頁十筆,所以搜尋 Harry Potter 會顯示全部七本正傳,而不是前五筆。
- `POST /books` 改用 `get_book_details` 查證 ISBN,不再重跑搜尋 —— 使用者選的候選
  可能來自第 7 頁。
- 159 個測試通過。semgrep 255 條規則 0 findings,包含兩個新檔(它預設只掃 git 已追蹤
  檔案,會跳過)。

### 剩餘工作

1. 補完被中斷的瀏覽器檢查:Title/Author 選單與 Previous/Next 已驗證有正確渲染、
   也確認會打到正確的端點,但**還沒在瀏覽器裡實際點過**。
2. Commit 並 push。
3. 測試部署版本前先硬重新整理。
4. 在 `DESIGN.md` 記錄 Inspector 對 `search_by_author` 與 `get_book_details` 的
   discovery 證據 —— 目前那裡註明尚未記錄。

## 細節三:MCP 搜尋工具的輸入正規化

Emma Zhou 標記 critical。對應 Must Have 順序 6。

### 留言內容

只有空白檢查與長度限制。沒有處理前後特殊符號、連續空白、換行或控制字元。原始輸入
直接送到 Open Library API。

### 成立的部分

缺漏是真的。`mcp_server/server.py` 只做 `query = raw.strip()`,所以
`"Harry\n\nPotter"` 和 `"Harry    Potter"` 會原樣送出。

### 不成立的部分

「造成 upstream API 請求畸形」不成立。查詢字串是以 httpx 的 `params` 傳遞,httpx 會
做 percent-encoding,換行會變成 `%0A`,無法破壞請求行或注入參數。**不應該把這件事
描述成請求完整性問題,因為它不是** —— 建立在錯誤前提上的修法很難 review。

真正該修的理由:

- **匹配品質。** 連續空白與散落的控制字元會被當成查詢的一部分送進搜尋索引,只會
  讓匹配變差。
- **日誌與快取雜訊。** 同一本書的兩種寫法變成兩個不同字串。

我們判斷這屬於 nitpick 到 suggestion 之間,不是 critical。這裡記錄不同意見,而不是
默默改掉評級。

### 做法

1. 在 `mcp_server/server.py` 加一個正規化 helper,在 `strip()` 之後、長度檢查之前
   套用,讓長度限制量到的是真正送出去的字串:
   - 移除 Unicode 控制字元與其他不可列印字元;
   - 把任何連續空白(含換行、tab)壓成一個空格。
2. 套在 `_search_result` —— 兩個搜尋工具本來就共用它,這樣兩者不會走鐘。
   `get_book_details` 維持自己更嚴格的規則:ISBN 應該只留數字與 `X`,
   `app/details.py` 的 `normalise_isbn` 已經做了。
3. **不要移除標點。** 書名合理地會有 `:`、`'`、`&`、`.`,而 `_author_tokens` 在比對
   作者名時本來就已經忽略標點。

### 檔案

`mcp_server/server.py`。若 helper 該放在 `normalise` 旁邊則含 `app/details.py`。

### 測試

加到 `tests/test_mcp_server.py`:

- 含換行、tab、連續空白的查詢,送到搜尋函式時是單一空格的字串;
- 只有控制字元的查詢被當成空白拒絕,而且不會呼叫目錄;
- 長度限制在壓縮**之後**套用,所以 400 個空格加一個短書名應該被接受;
- 含 `:` 與 `'` 的書名原樣通過。

### 完成條件

兩個搜尋工具正規化行為一致、上述測試通過、長度限制量的是正規化後的字串。

## 細節四:MCP 工具的一般例外處理

Emma Zhou 標記 suggestion。對應 Must Have 順序 5。

### 留言內容

只攔 `LookupUnavailable`。timeout、連線失敗、HTTP 4xx/5xx、JSON 解析失敗都沒處理,
未攔的頂層例外會讓 MCP server 程序崩潰並使 MCP client 完全斷線。

### 成立的部分

`_search_result` 與 `get_book_details` 確實只攔 `LookupUnavailable`,其他例外會往外傳。

### 不成立的部分

兩個所述成因都實測過,都不成立。

**列出的網路錯誤已經處理了。** `app/openlibrary.py:83` 攔 `httpx.HTTPError`,那是
timeout、連線失敗、以及 `raise_for_status` 丟出的 `HTTPStatusError` 的**基底類別**;
第 85 行攔 `ValueError`,涵蓋 JSON 解析失敗。全部轉成 `LookupUnavailable`,而工具有攔。

**server 不會崩潰。** 直接測過 —— 讓搜尋函式透過 FastMCP 的 in-memory client 丟出
`RuntimeError`:

```
is_error: True
text    : Error calling tool 'search_book': an unexpected bug, not a LookupUnavailable
structured: None
後續呼叫仍可用: Error: isbn must not be blank.
```

FastMCP 攔了下來、把結果標記為錯誤,而且同一個 client 的下一次呼叫照樣能用。
沒有程序崩潰,也沒有斷線。

### 真正的問題,而且值得修

上面那段輸出反而暴露出兩個真實缺陷,都比留言所述更精確,而且它提議的修法剛好對症:

1. **原始例外訊息傳到了 client。** `DESIGN.md` 明載這些工具「不揭露原始例外或
   Open Library 回應 JSON」,`LookupUnavailable` 那條路徑對此很小心。非預期的例外
   繞過了這個承諾,把內部文字直接洩漏給 AI client。
2. **`structured_content` 是 `None`。** 我們自己的 `app/mcp_client._call_tool` 要求
   它必須是 dict,否則丟 `MCPUnavailable`。網頁應用程式會存活(退回 seed),但它是
   經由一個壞掉的封包走到那裡,而不是走本來就為此存在的 `unavailable` 狀態。

### 做法

1. 在 `_search_result` 與 `get_book_details` 現有的 `LookupUnavailable` 子句**之後**
   加一個 `except Exception`,回傳標準的 `_unavailable()` 結果,並用
   `logger.exception` 在伺服器端記錄細節,讓它可診斷但不外洩。
2. 為 `mcp_server/server.py` 加一個 logger,它目前沒有。
3. **保留 `LookupUnavailable` 作為獨立子句。** 目錄故障是預期的,我們的對應程式碼
   有 bug 不是,日誌應該說得出是哪一種。

### 檔案

`mcp_server/server.py`。

### 測試

加到 `tests/test_mcp_server.py` 與 `tests/test_search_paging.py`:

- 搜尋函式丟 `RuntimeError` 時得到 `status: "unavailable"`,structured content 存在,
  且原始訊息不出現在文字裡;
- `get_book_details` 同上;
- `app.mcp_client` 把它轉成 `MCPUnavailable`,而 `lookup` 接著退回 seed。

### 完成條件

任何非預期例外都不可能讓工具回傳沒有 structured `unavailable` 封包的結果,
且工具文字裡不出現任何內部訊息。

## 細節五:`_format_book` 重複了欄位清單

Emma Zhou 標記 nitpick。**同意留言主體。** 對應 Should Have。

### 問題

`mcp_server/server.py` 把一本書的欄位寫了兩次:`_format_book` 產生可讀文字,
`_book_payload` 產生結構化 dict。要加一個出版社欄位就得改兩處,而且兩者會走鐘。
換行字元硬寫在 `join` 裡。

### 做法

把欄位順序以 `(label, value)` 配對宣告一次,然後兩種輸出都從它衍生:可讀文字用
label 排版,payload 用機器名當 key。一份清單、兩種呈現,新增欄位只改一處。

**建議的 `LINE_BREAK = "\n"` 常數不值得加。** `"\n".join(...)` 是 Python 慣用寫法,
比多一層間接更好讀;而且欄位清單共用之後,換行只會出現在一個地方。這裡記錄不同意見。

### 檔案

`mcp_server/server.py`。

### 測試

`tests/test_mcp_server.py` 與 `tests/test_author_search.py` 已經同時斷言可讀文字與
結構化 payload。它們應該**不用改就通過** —— 這正是這個重構的意義。再加一個測試斷言
兩種輸出描述同一組欄位,讓未來的新欄位不可能只加到其中一邊。

### 完成條件

欄位名稱與順序只宣告一次,而且既有斷言仍然通過。

## 細節六:在 `seed/books.json` 加 id 欄位

Emma Zhou 標記 nitpick。**建議不要做。** 底層觀察是對的,但結論不符合這個檔案的角色。
對應 Won't Have 與 Should Have 的回覆留言項。

### 留言內容

每一筆缺少自動遞增的唯一 id,單靠 ISBN 當唯一識別。一本書可能有多個不同 ISBN 的版本,
所以 ISBN 不能當穩定主鍵,後續 CRUD 很可能主鍵衝突。

### 為什麼這個修法不適用

`seed/books.json` 不是資料表,也從來不會變成帶有自己識別碼的資料列。它是網路不可用時
代替 Open Library 的離線目錄。`app/lookup.py:84-88` 只從每一筆讀四個 key 來建
`BookDetails`,和真實目錄產生的是同一個 value type。**加在檔案裡的 id 不會被任何
程式碼讀取。**

書本來就有主鍵。`app/db.py` 給 `books` 表一個 SQLite `INTEGER PRIMARY KEY`,在
insert 時指派。給 seed 加 id 會製造出第二套對資料庫毫無意義的編號,比沒有更糟。

所以「主鍵衝突」的風險並不像所述那樣存在:seed 提供 metadata,不提供 key。

### 留言裡真正的重點,我們該記下來

「一本書可能有多個不同 ISBN 的版本」是真的,而且確實影響我們 —— 透過
`identity_key`,它的值是 `isbn:<normalised>`。同一部作品的兩個版本會是兩筆資料列。

這是**刻意的設計而非疏漏** —— `CLAUDE.md` 明載「Allow books with the same title
when their ISBNs are different」—— 而且這正是讓人能追蹤自己手上那本平裝本、而不是
一個抽象作品的原因。

代價在分頁結果裡看得見:`author=J. K. Rowling` 回傳 421 筆,其中很多是同樣七本小說的
版本與譯本。把版本歸到作品之下會是真正的改善,而 Open Library 也提供了 work key
(`key`,例如 `/works/OL82563W`)可以支撐這件事。

那是產品變更,不是 nitpick。做法:回覆留言說明為什麼 seed 裡的 id 不會被讀取,
把「按 work 分組版本」作為獨立 backlog 項目寫進 `DESIGN.md` 7.7,現在不改程式碼。

### 完成條件

留言已有書面回覆,且 `DESIGN.md` 未來工作裡有「按 work 分組版本」項目。
