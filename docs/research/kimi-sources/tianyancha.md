# tianyancha

**Description:** 天眼查企业数据平台 - 支持226个API接口的动态调用平台。提供全面的企业工商信息、股东信息、司法风险、知识产权、经营数据等查询服务。通过智能API搜索和动态调用机制，用户可以轻松发现和使用各种企业数据接口

## Available APIs

### tianyancha_api_search

**Description:** 根据用户查询关键词搜索匹配的天眼查API接口以及接口所需要的参数，帮助用户发现和选择合适的企业数据API。
尽可能使用多个关键词搜索，如&#39;企业基本信息,股东信息&#39;、&#39;司法风险,年报&#39;、&#39;专利,招投标&#39;等，减少工具调用的次数
不应使用任何含特定公司名称的关键词进行查询，如&#39;百度,阿里巴巴&#39;等
返回结果包括：API名称、API描述、API所需要的参数、API的示例URL


**Required Parameters:**
- `query` (string): 查询关键词，如&#39;企业基本信息,股东信息&#39;、&#39;司法风险,年报&#39;、&#39;专利,招投标&#39;等，不允许使用公司名作为查询词

**Optional Parameters:**
- `limit` (string): 返回结果数量限制，默认10个，最大20个 (default: 10)

---

### tianyancha_company_search

**Description:** 注意**仅用于不知道公司全称的时候才调用**，常见公司或者已知公司全称的时候不要使用此工具！接使用api_call查询公司信息
如果用户已给出公司全名、通过网络搜索、模型知识、上下文等，知道公司全称的时候，不要使用此工具！直接使用api_call查询公司信息(如遇到query为知名公司特斯拉、网易、腾讯等公司简称的时候，不需要搜索，直接使用全称查询)
只有不知道公司全名时，使用此工具搜索获得准确的公司信息，如注册号,经营状态,统一社会信用代码,成立日期,注册资本,机构类型,公司名,公司id,组织机构代码,省份,法人,匹配原因,总数


**Required Parameters:**
- `search_keyword` (string): 搜索关键词，可以是公司名称、注册号、统一信用代码等
- `file_path` (string): 保存搜索结果的CSV文件路径

**Optional Parameters:**
- `page_size` (integer): 每页返回条数，默认20，最大20 (default: 20)
- `page_num` (integer): 当前页数，默认第1页 (default: 1)

---

### tianyancha_api_call

**Description:** ### 天眼查API调用工具
根据API名称和参数调用指定的天眼查API接口，将返回结果保存为CSV文件。
必须使用完整的企业全称/信用代码等以获得最准确的查询结果，不允许使用公司简称，如特斯拉、网易、腾讯等公司简称。
使用api_call_params中的keyword查询公司的时候，每次只允许查询一个公司，不允许用逗号、顿号、分号或换行传入多个公司。
**重要提示**: 此工具的名称固定为 &#34;tianyancha_api_call&#34;，不要使用从tianyancha_api_search返回的API名称作为工具名。


**Required Parameters:**
- `api_call_name` (string): 要调用的API名称（从tianyancha_api_search结果中获取的完整API名称），如果不知道API名称，可以使用tianyancha_api_search搜索，如果不知道公司全称/信用代码的时候，使用搜索-搜索接口
- `api_call_params` (object): API调用参数字典，根据具体API要求提供参数，包括但不限于：
- keyword: 搜索关键字（企业名称、注册号、统一信用代码等），必须使用完整的企业全称以获得最准确的查询结果；每次只允许一个公司，不允许传入多个公司名
- pageNum: 当前页数（默认1）- 分页API需要  
- pageSize: 每页条数（默认20，最大20）- 分页API需要
- 其他特定参数根据API要求提供

- `file_path` (string): 保存结果的CSV文件路径，数据将以结构化格式保存到此文件

---

