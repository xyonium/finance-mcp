# yuandian_law

**Description:** 元典法律数据库（yuandian_law）。提供中国法律法规与司法案例检索：宪法/法律/司法解释/部门规章等各效力层次的中国法律法规语义与关键词检索及详情查询；普通与权威案例的检索及详情查询。适用于法律案例分析/律师咨询/法律研究/合规分析等各类法律场景。

## Available APIs

### yd_law_search

**Description:** ### 元典法律法规检索 / 详情
检索中国法律法规或获取详情，按 mode 选择具体接口：
- semantic：法律法规语义检索（自然语言问题），底层 /open/law_vector_search
- ft_keyword：法条关键词检索（命中具体法条条文），底层 /open/rh_ft_search
- fg_keyword：法规关键词检索（命中整部法规，可不传 query 仅按过滤项），底层 /open/rh_fg_search
- ft_detail：法条详情，底层 /open/rh_ft_detail。可按 id 或（law_name + article_number）查询
- fg_detail：法规详情，底层 /open/rh_fg_detail。可按 id 或 law_name 查询；返回含法规附件列表（每条含附件标题与附件正文，已归一为「附件」列）

关键词模式可选过滤：effect_levels（效力级别）、validities（时效性）、region（地域）、law_name、发布/实施日期区间、top_k。
详情模式：id 与 law_name 不能同时为空；ft_detail 没有 id 时还须提供 article_number；详情类不接受 top_k。

检索路径选择（law_name vs query）：要「按法规名称」筛选或定位，请优先用 law_name（对应上游 fgmc，
对法规标题有专门处理，并自动覆盖法规标题/附件标题/附件内容的合并命中）；要「按法规正文/附件内容」做
全文关键词检索，用 query（对应上游 keyword，走通用全文检索，对标题字段无特殊处理）。二者是独立链路，按需选用。


**Required Parameters:**
- `mode` (string): 模式：semantic（法律法规语义） / ft_keyword（法条关键词） / fg_keyword（法规关键词） / ft_detail（法条详情） / fg_detail（法规详情）
 (options: semantic, ft_keyword, fg_keyword, ft_detail, fg_detail)
- `file_path` (string): 保存结果的绝对路径（CSV 格式）

**Optional Parameters:**
- `effect_levels` (array): ft_keyword / fg_keyword / semantic 可选，一级效力级别数组（多值为或关系）。 semantic 模式直接传给上游；keyword 模式工具内部按空格拼接传给上游。 可选值：宪法、法律、司法解释、行政法规、监察法规、部门规章、党内法规、 军事法规规章、立法机关工作文件、行政机关工作文件、行业/团体规范、 地方性法规、自治条例和单行条例、地方司法文件、地方政府规章、 地方规范性文件、地方律协规定

- `id` (string): ft_detail / fg_detail 模式：文档 ID（法条 id 或法规 id），优先按 id 查询
- `law_name` (string): ft_keyword / fg_keyword：法规名称过滤（按空格拆分后法规标题需全部命中）。 按法规名称检索请优先用本参数而非 query：对应上游 fgmc，对法规标题有专门处理， 并自动覆盖法规标题/附件标题/附件内容的合并命中； ft_detail（id 为空时必填）：法规名称； fg_detail（id 为空时必填）：法规名称

- `validities` (array): ft_keyword / fg_keyword / semantic 可选，时效性数组（多值为或关系）。 semantic 模式直接传给上游；keyword 模式工具内部按空格拼接传给上游。 可选值：现行有效、失效、已被修改、部分失效、尚未生效

- `law_start` (string): semantic 模式可选，法条生效起始日期，格式 yyyy-MM-dd
- `publish_date_end` (string): ft_keyword / fg_keyword 可选，发布日期止，格式 yyyy-MM-dd
- `article_number` (string): ft_detail 模式（id 为空时必填）：法条号/名称，如「第十五条」
- `law_end` (string): semantic 模式可选，法条生效结束日期，格式 yyyy-MM-dd
- `effective_date_start` (string): ft_keyword / fg_keyword 可选，实施日期起，格式 yyyy-MM-dd
- `effective_date_end` (string): ft_keyword / fg_keyword 可选，实施日期止，格式 yyyy-MM-dd
- `top_k` (integer): 返回条数上限（工具层上限 50；超过 50 截断到 50，&lt;=0 视为未传走默认值）。 按 mode 分别取默认值：semantic 默认 30（作为 return_num 传给底层接口）， ft_keyword / fg_keyword 默认 10；详情类 mode 不接受此参数（传入会报错）。 想浏览常见结果传 10-30，想看更多再传到 50。

- `rewrite_flag` (boolean): semantic 可选，是否对查询做改写，默认 true (default: true)
- `refer_date` (string): ft_detail / fg_detail 可选，参考日期，格式 yyyy-MM-dd
- `region` (string): ft_keyword / fg_keyword 可选，地域过滤（按空格拆分多值，命中任一即可）。 可选值：中央、北京、天津、河北、山西、内蒙古、辽宁、吉林、黑龙江、上海、 江苏、浙江、安徽、福建、江西、山东、河南、湖北、湖南、广东、广西、海南、 重庆、四川、贵州、云南、西藏、陕西、甘肃、青海、宁夏、新疆

- `publish_date_start` (string): ft_keyword / fg_keyword 可选，发布日期起，格式 yyyy-MM-dd
- `query` (string): 检索内容。semantic 必填（自然语言问题）； ft_keyword 必填（关键词，多关键词以空格分隔）； fg_keyword 可选（关键词走全文检索，命中范围含法规正文、法规标题、附件标题与附件内容； 不传则按过滤项返回法规列表。若仅想按法规名称筛选，请改用 law_name 而非 query）； 详情模式不使用此字段。

- `search_mode` (string): 关键词拼接模式（仅 ft_keyword / fg_keyword）：AND / OR，默认 AND (default: AND) (options: AND, OR, and, or)

---

### yd_case_search

**Description:** ### 元典案例检索 / 详情
检索中国司法裁判案例或获取案例详情，按 mode 选择具体接口：
- semantic：案例语义检索（自然语言问题），底层 /open/case_vector_search
- keyword_pt：普通案例库关键词检索，底层 /open/rh_ptal_search
- keyword_qw：权威案例库（典型案例/参考案例）关键词检索，底层 /open/rh_qwal_search
- detail_pt：普通案例详情，底层 /open/rh_case_details?type=ptal
- detail_qw：权威案例详情，底层 /open/rh_case_details?type=qwal

关键词模式可按案号、标题、案由、法院、案件类别、行政区划、文书种类、日期区间等过滤。
详情模式：id 与 case_number 至少提供一个，优先 id；上游单次最多返回 10 条，且不接受 top_k。


**Required Parameters:**
- `mode` (string): 模式：semantic（语义） / keyword_pt（普通案例关键词） / keyword_qw（权威案例关键词） / detail_pt（普通案例详情） / detail_qw（权威案例详情）
 (options: semantic, keyword_pt, keyword_qw, detail_pt, detail_qw)
- `file_path` (string): 保存结果的绝对路径（CSV 格式）

**Optional Parameters:**
- `courts` (array): keyword_pt / keyword_qw 可选，经办法院/承办单位（多值为或关系）
- `doc_types` (array): 文书种类数组（多值为或关系）。 可选值： keyword_pt / keyword_qw：判决书、裁定书、调解书、决定书； semantic： 可传中文名：判决书、裁定书、调解书、决定书、通知书、支付令、申请书、起诉书、抗诉书、起诉状、上诉状； 也可直接传编码字符串：1=判决书、2=裁定书、3=调解书、4=决定书、5=通知书、6=支付令、 7=申请书、8=起诉书、9=抗诉书、10=起诉状、11=上诉状。

- `cited_articles_mode` (string): keyword_pt 可选，cited_articles 拼接模式：and / or，默认 and (default: and) (options: and, or)
- `court_names` (array): semantic 可选，法院名称列表
- `only_authoritative` (boolean): semantic 可选，是否仅典型/权威案例库（默认 false 即同时包含普通+权威） (default: false)
- `query` (string): semantic 必填（自然语言问题）；其它模式不使用此字段
- `causes` (array): keyword_pt / keyword_qw / semantic 可选，案由数组（多值为或关系）
- `provinces` (array): keyword_pt / keyword_qw / semantic 可选，省级行政区数组（多值为或关系）。 semantic 模式上游仅接受单值，工具内部取数组首项。 可选值：北京、天津、河北、山西、内蒙古、辽宁、吉林、黑龙江、上海、江苏、 浙江、安徽、福建、江西、山东、河南、湖北、湖南、广东、广西、海南、重庆、 四川、贵州、云南、西藏、陕西、甘肃、青海、宁夏、新疆、最高、新疆生产建设兵团

- `city` (string): semantic 可选，市级行政区
- `top_k` (integer): 返回条数上限（工具层上限 50；超过 50 截断到 50，&lt;=0 视为未传走默认值）。 按 mode 分别取默认值：semantic 默认 30（作为 return_num 传给底层接口）， keyword_pt / keyword_qw 默认 10；详情类 mode 不接受此参数（传入会报错）。 想浏览常见结果传 10-30，想看更多再传到 50。

- `id` (string): detail_pt / detail_qw 可选，案例 ID（与 case_number 至少有一个非空）
- `full_text` (string): keyword_pt / keyword_qw 可选，全文关键词（多关键词以空格分隔）
- `analysis_text` (string): keyword_pt 可选，分析过程关键词（按 search_mode 拼接）
- `title` (string): keyword_pt / keyword_qw 可选，标题（按空格拆分后需全部命中）
- `case_category` (string): keyword_pt / keyword_qw / semantic 可选，案件类别。 keyword_pt / keyword_qw 模式工具内部映射为上游 ajlb 字段； semantic 模式工具内部映射为上游 wenshu_type 字段。 可选值：刑事案件、民事案件、行政案件、执行案件、管辖案件、 国家赔偿与司法救助案件、强制清算与破产案件、国际司法协助案件、 非诉保全审查案件、其他案件

- `cited_articles` (array): keyword_pt 可选，援引法条数组（形如「中华人民共和国刑法第二条」）， 每个元素只能包含一个法条，且法条编号为中文（如「第二条」）

- `judgment_date_start` (string): keyword_pt / keyword_qw / semantic 可选，结案/裁判日期起，格式 yyyy-MM-dd
- `case_number` (string): keyword_pt / keyword_qw 可选，按案号过滤； detail_pt / detail_qw 可选，按案号查询（id 为空时使用）

- `search_mode` (string): keyword_pt / keyword_qw 可选，关键词拼接模式：and / or，默认 and (default: and) (options: and, or)
- `judgment_date_end` (string): keyword_pt / keyword_qw / semantic 可选，结案/裁判日期止，格式 yyyy-MM-dd
- `court_level` (string): semantic 可选，法院层级，如「最高/高级/中级/基层」
- `rewrite_flag` (boolean): semantic 可选，是否对查询做改写，默认 true (default: true)

---

