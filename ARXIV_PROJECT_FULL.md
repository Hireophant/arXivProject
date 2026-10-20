# arXiv Project — Toàn bộ đề bài và các milestone

Nguồn: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/  
Ngày tải và đối chiếu: 17/10/2026 (Asia/Bangkok). Bản cũ được tải ngày 11/10/2026.

Tài liệu này gộp các bản Markdown tải trực tiếp từ website môn học: trang tổng quan và cả ba milestone. Giữ nguyên nội dung tiếng Anh, ví dụ code, công thức, bảng, quy định và tiêu chí chấm điểm. Tiêu đề được điều chỉnh cấp để tiện đọc; liên kết MyST và trích dẫn được chuyển sang Markdown. Các trang tài liệu bên ngoài được giữ dưới dạng liên kết tham khảo.

## Những thay đổi so với bản 11/10/2026

Phần này là tóm tắt đối chiếu của nhóm tài liệu, không phải nội dung nguyên văn của đề bài. Các phần tiếng Anh bên dưới là nội dung đề hiện tại, tải ngày 17/10/2026; ngày đối chiếu không khẳng định ngày giảng viên sửa đề.

| Nội dung | Bản cũ | Bản hiện tại |
|:---|:---|:---|
| Nhãn thủ công (M3) | Ít nhất 5 publications, tổng ít nhất 20 labeled reference pairs | Ít nhất 5 publications, **mỗi publication ít nhất 20 labeled BibTeX entries**, tổng ít nhất 100 entries |
| Nhãn tự động (M3) | Ít nhất 10% phần dữ liệu còn lại, chưa làm rõ đơn vị | Ít nhất **10% số publications ngoài manual pool**; gán nhãn mọi BibTeX entry của mỗi publication được chọn |
| Ground truth (M3) | Mô tả nhãn nhị phân cho các cặp trong không gian m × n | Làm rõ từng hàng ứng với một labeled entry: một positive nếu có reference đúng, còn lại negative; không có match thì cả hàng negative; entry chưa có nhãn không tạo hàng |
| Đánh giá (M3) | Gọi là MRR, đã xét top 5 | Gọi rõ **MRR@5**; Q là số labeled BibTeX entries trong Test set; reference đúng không nằm trong top 5 thì entry nhận 0 |
| Dataset cuối | 7 bảng, gồm cả `sources` | **6 bảng**: `papers`, `references`, `elements`, `hierarchy`, `bibtex`, `predictions`; không còn bảng `sources` trong schema nộp cuối |
| Tên bảng | `paper_references`, `element_parents`, `bibtex_entries` | Lần lượt đổi thành `references`, `hierarchy`, `bibtex`; `arxiv_id` của `references`, `hierarchy`, `bibtex` được ghi rõ non-null |
| Nơi định nghĩa schema | Toàn bộ schema tập trung ở M3 | M1 định nghĩa `papers`, `references`; M2 định nghĩa `elements`, `hierarchy`, `bibtex`; M3 định nghĩa `predictions` và tổng hợp 6 bảng |
| Dữ liệu làm việc (M1/M2) | Gợi ý các file như `metadata.json`, `references.json`, `hierarchy.json`, `refs.bib` | Bỏ ví dụ layout/file JSON cụ thể; nhóm tự tổ chức dữ liệu trung gian, giữ đủ thông tin để xuất các bảng cuối |
| Discovery (M1) | Giới thiệu API, OAI-PMH, Kaggle | Nêu rõ chỉ cần resolve dải ID được giao và tìm mọi version; **không yêu cầu harvest toàn arXiv**; suffix version mới nhất từ lookup base ID giúp xác định số version |
| Lọc source và references (M1) | Khuyên bỏ hình; chưa phân biệt rõ references local và bảng xuất | Chỉ extract `.tex`/`.bib`, giữ nguyên lệnh figure và `\includegraphics` trong TeX. Giữ mọi crawled reference ở local; chỉ reference có arXiv ID vào bảng `references`. Bổ sung hướng dẫn fields Semantic Scholar dạng phẳng, không dùng nested `authors.name` |
| Parse và dedup (M2) | Theo compilation path, chia câu, dedup liên version | Chỉ rõ root chứa `\documentclass`, theo `\input`/`\include` bắc cầu và không theo lệnh đã comment; không tách câu trong math, commands, viết tắt, URL, số thập phân. Bổ sung ví dụ union BibTeX fields và shared elements với parent khác theo version |
| Version rỗng và báo cáo | M1 đã yêu cầu giữ record nếu không có TeX; M2 chưa nói rõ | M2 ghi rõ version không có TeX không sinh elements nhưng phải ghi nhận là empty, không bỏ qua; report thêm version coverage. M1 bổ sung ví dụ đo RAM/disk có thể kiểm chứng, công cụ chỉ là gợi ý |
| Hướng dẫn download | Có mục “Kaggle Mirror for Public Access” và ví dụ queue download | Bỏ mục này và ví dụ; phần Kaggle metadata discovery vẫn còn |

Các yêu cầu cốt lõi vẫn giữ: crawl tất cả versions, một code repository chung, Jupyter Book riêng cho M1/M2 với hình/bảng sinh lúc build, không nộp data trung gian, benchmark CPU-only trên Colab, split theo publication (Test và Validation mỗi tập gồm 1 bài manual + 1 bài automatic), và poster một trang A2 dọc trong file PPTX.

## Ghi chú triển khai của nhóm — OAI-PMH arXivRaw và cache/Kaggle cho ngày references

Cập nhật triển khai 20/10/2026: code M1 dùng `GetRecord` tại `https://oaipmh.arxiv.org/oai` với `metadataPrefix=arXivRaw` cho metadata và mọi versions của bài được giao. Ngày v1 references dùng cache có bằng chứng, index Cornell Kaggle local và OAI fallback; chi tiết và chuyển đổi dữ liệu cũ ở [thiết kế tối ưu](docs/milestone1/TOI_UU_REFERENCE_DATES.md). Ví dụ `arXiv`/Sickle trong đề bên dưới là minh họa tổng quát; tài liệu chính thức xác nhận `arXivRaw` chứa lịch sử versions. `datestamp` của OAI là ngày metadata thay đổi, không phải ngày gửi bài.

Nhịp hiện hành: tối thiểu 3 giây/request, một kết nối tại một thời điểm; code mặc định 3,1 giây và tôn trọng Retry-After. Nguồn kiểm tra ngày 17/10/2026: [OAI-PMH chính thức](https://info.arxiv.org/help/oa/index.html), [quy định rate limit](https://info.arxiv.org/help/api/tou.html). Đây là ghi chú của nhóm; phần tiếng Anh bên dưới vẫn giữ nội dung đề được tải.

## Mục lục

1. [Đề bài tổng quan](#project-overview)
2. [Milestone 1 — Data Crawling](#milestone-crawling)
3. [Milestone 2 — Hierarchical Parsing and Standardization](#milestone-parsing)
4. [Milestone 3 — Reference Matching Pipeline](#milestone-matching)

---

<a id="project-overview"></a>

## arXiv Project — Problem Statements

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/index-e620bc33e2e4c33e19205dd3c9f27ce3.md)

### Logistics

The project is a **group work**. Each milestone is submitted as a group via Moodle:

- **Shared code repository**: one public code repository per group serves the whole project, with each milestone's code committed to it cumulatively so the commit history documents the group's progress. Milestones 1 and 2 paste its link via Moodle together with the report link, and Milestone 3 submits it together with the poster and the dataset.
- **Jupyter Book for Milestones 1 and 2**: the milestone reports form one public **Jupyter Book**, hosted on its own separate repository's GitHub Pages. Milestone 1's report is the book's first section and Milestone 2 adds the next section, and report figures and tables must be generated during book compilation.
- **Final data submission**: there is no intermediate data submission. The fully processed data is hosted as a **Hugging Face dataset** of sharded Parquet tables, with the table set specified across the milestone statements, papers and references in Milestone 1, elements, hierarchy and bibtex in Milestone 2, and predictions in Milestone 3, while hosting follows the instructions given by the Lab Instructors. The dataset link is submitted via Moodle.
- **Final grading**: a **poster session**. Each group submits one pptx file containing a single-page poster in the form factor of **portrait A2** for review, and upon acceptance the group prints the poster and presents it at the poster session.

### Milestones

- **[Project Milestone 1 — Data Crawling](#milestone-crawling)**: build the raw corpus, discover the assigned arXiv papers in the range provided by the Lab Instructors, crawl every version of each publication with its full-text LaTeX sources, metadata, and reference metadata, and analyze the scraped corpus.
- **[Project Milestone 2 — Hierarchical Parsing and Standardization](#milestone-parsing)**: structure the corpus, parse each version into a hierarchical tree, standardize the content, convert `\\bibitem` references into BibTeX, deduplicate across versions, and analyze the processed data.
- **[Project Milestone 3 — Reference Matching Pipeline](#milestone-matching)**: run the machine learning pipeline, clean, label, engineer features, model, and evaluate a reference-matching system scored with Mean Reciprocal Rank @5, written MRR@5.

Milestone-specific requirements and submission formats are detailed in each milestone page.

### Regulations

Ensure your code is well-documented with clear comments. You can use online documents for reference, but you must provide complete citations. You are free to discuss your topics with classmates, but your work must be implemented and interpreted according to your own understanding.

**Any milestone will be graded zero if there is any dishonest behaviour detected.**

---

<a id="milestone-crawling"></a>

## Project Milestone 1 — Data Crawling

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/crawling-8fad9ed19f51add44df0ebce57dffab5.md)

## Objectives

In this milestone, students will employ the knowledge about data scraping, also called crawling, obtained from the theoretical lectures to scrape an online repository. This practice is expected to help you convert that knowledge into useful skills about the engineering aspect of your data science journey. However, do not think that this milestone, as well as the others, will cover all the necessary skills you should know before joining realistic projects, so you must continue learning even after the completion of this course!

This year's target is arXiv, the open-access repository of more than two million papers. Scraping arXiv is already a known practice in data engineering courses, though most of them exclusively focus on metadata rather than the full-text resources. Here, you will get ahead of them by collecting the **full-text LaTeX sources** of the papers rather than the hard-to-process PDFs. The corpus built in this milestone is the working foundation for the parsing and machine learning work of Milestones 2 and 3, so make the crawl complete and correctly organized.

## Description

This milestone consists of three main areas: resolving the assigned paper entries, downloading their full-text source files, and extracting structured reference information.

### Entry Discovery

The first step in any arXiv crawling workflow is to identify which papers to collect. In this project the assigned range arrives as plain arXiv IDs, so these methods are a toolbox rather than a task: the API resolves the assigned IDs into paper metadata and reveals each paper's version list, while OAI-PMH and the Kaggle snapshot show how the same discovery is done at repository scale. Implementing a full repository-scale harvest is *not* part of this milestone.

#### arXiv API for Targeted Discovery

The arXiv API at <http://export.arxiv.org/api/query> provides an HTTP interface for retrieving information on papers based on search keywords, authors, or categories. It returns results in Atom XML format, which can be parsed programmatically. This method is particularly convenient for targeted queries or daily updates of new submissions.

**Key Parameters and Usage** The arXiv API accepts several useful parameters:

- `search_query`: Field-specific search such as `ti:neural AND cat:cs.AI`

- `id_list`: Comma-separated arXiv IDs for direct lookup

- `start`, `max_results`: For pagination control

- `sortBy`, `sortOrder`: Sorting criteria such as submission date

The library `arxiv.py` allows flexible interaction with this API [^crawling-arxiv-api-manual][^crawling-arxiv-api-basics][^crawling-arxiv-py-github]. Two practical notes matter for this year: the API etiquette asks for modest request rates, so wait at least 3 seconds between successive calls and use one connection at a time [^crawling-arxiv-api-tou], and the client used below enforces this delay automatically. The library also went through breaking changes from version 2.x through version 4.x in 2025 and 2026, removing the old patterns `search.results()` and `Result.download_pdf()` / `Result.download_source()` in version 4.0.0 of May 2026, so always use the modern `client.results(search)` style and consult the library's README for the current behavior.

**Example arXiv API querying function:**

```
import arxiv

def find_papers(keyword, limit=5):
    search = arxiv.Search(query=f"all:{keyword}",
                          max_results=limit,
                          sort_by=arxiv.SortCriterion.SubmittedDate)
    return [paper.title for paper in arxiv.Client().results(search)]

# Example usage
titles = find_papers("quantum computing")
print(titles)
```

Results are returned as structured objects containing metadata such as title, authors, abstract, and arXiv ID. Two API facts matter for the assigned range. First, an `id_list` lookup on the base ID returns the identifier of the *latest* version, for example `2310.12345v4` as the identifier of the fourth revision, so reading this suffix tells you how many versions a paper has, which drives the every-version requirement below. Second, an individual version is fetched alone through the versioned `/src/` endpoint described in the download section.

#### OAI-PMH for Metadata Harvesting

The Open Archives Initiative Protocol for Metadata Harvesting, abbreviated OAI-PMH, enables systematic retrieval of metadata from arXiv. It is the officially supported bulk-access protocol for academic repositories and is well suited for automated metadata gathering. Since March 2025 the arXiv endpoint lives at <https://oaipmh.arxiv.org/oai>. The old address `export.arxiv.org/oai2` was retired during arXiv's cloud migration and may only redirect, so point new harvesters at the new endpoint [^crawling-oai-pmh-arxiv][^crawling-oai-pmh-cutover].

**Main Concepts** OAI-PMH uses a set of *verbs*, commands that request data from the repository:

- `Identify`: Get information about the repository

- `ListRecords`: Retrieve multiple records including metadata

- `ListIdentifiers`: Retrieve identifiers (IDs) only

**Selective Harvesting** Harvests can be scoped by date range with the `from` and `until` parameters, by category such as `set=cs`, and by metadata format where the `arXiv` prefix is recommended. One behavioral change of the March 2025 rewrite matters in practice: resumption tokens no longer encode the collection size and *expire daily*, so design a full sweep to finish within a day or to resume gracefully from saved state. The same 3-second pacing applies here as well.

**Basic OAI-PMH retrieval function, endpoint updated March 2025:**

```
from sickle import Sickle

def harvest_arxiv_records(date_from, date_to):
    sickle = Sickle("https://oaipmh.arxiv.org/oai")
    records = sickle.ListRecords(metadataPrefix='arXiv',
                                 from_=date_from, until=date_to)
    return [r.metadata for r in records]
```

This example shows how to obtain a structured list of metadata dictionaries that can later be stored as JSON or a database. Resumption tokens handle pagination automatically, so harvests of thousands of records run without manual page management, and for large time-bounded sweeps the protocol far outpaces the API [^crawling-oai-pmh-arxiv].

#### Kaggle Dataset for Pre-Aggregated Metadata

The Cornell arXiv dataset available on Kaggle at <https://www.kaggle.com/datasets/Cornell-University/arxiv> provides pre-collected metadata for well over two million papers. It can be used directly without any API calls and is ideal for local data processing or exploratory searches [^crawling-kaggle-arxiv].

**Data Handling and Example** The dataset is provided in JSON lines format, where each line represents one paper's metadata. It can easily be loaded into Python for filtering and analysis using pandas:

**Reading and filtering arXiv metadata via Kaggle dataset:**

```
import pandas as pd
import json

def load_arxiv_metadata(file_path, keyword):
    with open(file_path, 'r') as f:
        records = [json.loads(line) for line in f]
    df = pd.DataFrame(records)
    return df[df['title'].str.contains(keyword, case=False)]
```

After loading, students may extract the fields they need such as titles, abstracts, authors, or categories for the selected subset of papers.

#### Summary

| **Method**     | **Interface Type**  | **Example Tool or Library** |
|:---------------|:--------------------|:----------------------------|
| arXiv API      | HTTP/XML Endpoint   | arxiv.py                    |
| OAI-PMH        | Metadata Protocol   | Sickle                      |
| Kaggle Dataset | Static JSON Dataset | pandas                      |
*Summary of entry discovery methods*

### Full-Text Source Download

Once you have identified the list of papers to collect, the next step is to obtain their full source files. The goal here is to retrieve the original submission TeX sources, either archived in `.tar.gz` format or in other forms, without modifying their contents. Note that there are many types of sources other than `.tar.gz`, and you will need to identify which types contain the `.tex` or `.bib` files, since those are the only file types the working corpus keeps as the Requirement specifies. Other forms such as PDF files or `.docx` Word documents may not be convertible into TeX files, and for such versions you should keep an empty record in the corpus rather than dropping the publication.

arXiv provides source files for approximately 97% of its submissions, and the rest arrive as PDF-only [^crawling-arxiv-html-paper][^crawling-arxiv-whytex]. A source archive is a gzipped tar containing the `.tex` files, often several and linked through `\input` or `\include`, the `.bib` bibliography files, style and class files, occasionally a pre-compiled `.bbl`, and the figure binaries. Source archives are served by the dedicated mirror `export.arxiv.org`: the preferred endpoint `https://export.arxiv.org/src/{arxiv_id}` consistently returns a gzipped tar archive, and it also accepts *versioned* identifiers such as `.../src/2310.12345v2`, which is how every revision of a publication is retrieved individually [^crawling-arxiv-mimetypes]. Point automated downloads at this mirror and never at the main site `arxiv.org`, where aggressive crawling triggers automatic robot detection and 403 blocks, and use a descriptive User-Agent header with the same 3-second pacing.

#### arXiv API Download Using Python

The simplest and most common way to download a paper's full source archive is through the `arxiv.py` Python library, which wraps the API into user-friendly methods.

**Basic Workflow**

1.  Query the API with the paper's arXiv ID to retrieve its metadata.

2.  Download the source archive from the `/src/` endpoint for each revision identified through the API lookup. arxiv.py 4.x no longer ships a download method, so fetch the archive yourself, for example with `urllib` [^crawling-arxiv-py-github].

3.  Save the archive into the version's directory.

**Downloading an arXiv source file with arxiv.py version 4.x:**

```
import arxiv
import urllib.request

def get_source(arxiv_id, save_dir="./sources"):
    paper = next(arxiv.Client()
                     .results(arxiv.Search(id_list=[arxiv_id])))
    print(paper.title, paper.id)  # id ends with the latest version suffix, e.g. 2310.12345v4
    url = f"https://export.arxiv.org/src/{arxiv_id}"
    urllib.request.urlretrieve(url, f"{save_dir}/{arxiv_id}.tar.gz")

# Example usage: one call per version
get_source("2310.12345v1")
get_source("2310.12345v2")
```

#### Command-Line Download with arxiv-downloader

For users preferring direct commands over scripting, the open-source command-line utility `arxiv-downloader` provides a quick way to get both PDFs and sources. Installed via pip, it downloads source files using only the paper ID or URL [^crawling-arxiv-downloader].

**Example Usage**

```
arxiv-downloader 2302.06544 -s -d ./downloads
```

The flag `-s` ensures that source files are fetched rather than PDFs, and `-d` designates the output directory.

#### Amazon S3 Bulk Repository Access

arXiv maintains complete source archives within an Amazon Web Services S3 requester-pays bucket at `s3://arxiv/src/`. This interface is intended for large-scale retrieval, allowing structured downloads of `.tar` bundles containing multiple monthly paper packages [^crawling-arxiv-s3-bulk].

**Setup and Example Command** Before downloading, configure AWS credentials with `aws configure`. Then use:

```
aws s3 cp s3://arxiv/src/arXiv_src_2401_001.tar \
              ./bulk/ --request-payer requester
```

Each archive contains multiple submission source files grouped by upload date. The monthly chunks follow the naming pattern `arXiv_src_YYMM_NNN.tar`, and the complete archive is on the order of several TB and growing, so consult `arXiv_src_manifest.xml` for the exact chunk list before downloading. You can loop this process to download archives for consecutive months as needed. Alternatively, `s3cmd` provides a lightweight interface: `s3cmd get --recursive --requester-pays s3://arxiv/src/` retrieves all available source archives without manual iteration. A free mirror of the same sources also exists on Google Cloud Storage at `gs://arxiv-dataset`.

#### Summary

| **Method**   | **Access Interface**   | **Example Tool** |
|:-------------|:-----------------------|:-----------------|
| arXiv API    | REST via Python client | arxiv.py         |
| Command-Line | CLI utility            | arxiv-downloader |
| Amazon S3    | Bulk cloud storage     | awscli or s3cmd  |
*Available methods for retrieving arXiv source files*

### Extracting References

When working with arXiv papers, extracting structured reference information is essential for understanding citation relationships. This section introduces the Semantic Scholar API as a method to retrieve references and associated identifiers like arXiv IDs without direct LaTeX parsing.

#### Semantic Scholar

Semantic Scholar, developed by the Allen Institute for AI, indexes over 214 million papers and provides structured access to citation data through a free API [^crawling-semantic-scholar-api][^crawling-semantic-scholar-platform]. It excels in linking arXiv papers to broader academic graphs, offering fields such as titles, authors, years, and external identifiers. The API endpoint is `https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}`, where queries use the arXiv prefix for identification.

**Request Fields and Response** To obtain references, specify fields such as `references.title`, `references.authors`, `references.year`, `references.publicationDate`, `references.venue`, and `references.externalIds` in the query parameters, and request them flat because nested forms such as `authors.name` are rejected. Every referenced paper also returns its `paperId`, the Semantic Scholar identifier, and its `externalIds` dictionary carries the `ArXiv` key used by this project together with `CorpusId`, `DOI`, or other identifiers when they exist, so checking for `externalIds.ArXiv` decides whether a crawled reference becomes a row of the `references` table in the Requirement section. The response is a JSON object containing an array of references, each holding the requested fields. A simple function to query and extract basic reference data is shown below:

**Querying Semantic Scholar for references:**

```
import requests

def get_paper_references(arxiv_id):
    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}"
    params = {"fields": "references.title, references.authors, references.year, references.publicationDate, references.externalIds"}
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("references", [])
```

This retrieves the list of references for a given arXiv ID.

#### Extracting arXiv Identifiers

From the API response, arXiv IDs are found in the `externalIds` dictionary of each reference. The process involves iterating over the references array and checking for the presence of the `ArXiv` key.

**Handling Problematic Identifiers** Not every reference includes an arXiv ID, as some cite journal articles, books, or non-arXiv sources. Coverage is higher in fields like computer science, where arXiv is prevalent. Besides that, references published on arXiv before 2007 also possess a different scheme of indexing under the old `archive/YYMMNNN` format such as `hep-th/9901001`, so students should retain the original identifiers for such publications.

#### Rate Limits and Usage

The API enforces limits of 1 request per second and 100 requests per 5-minute window for unauthenticated use [^crawling-semantic-scholar-api]. Exceeding these triggers 429 errors, so implement delays and error handling. API key usage is permitted and will help you improve the runtime performance: the free tier shares one unauthenticated request pool that is subject to throttling during heavy use, while a free API key guarantees a steady 1 request/second, with higher limits available upon review.

**Accuracy Considerations** Semantic Scholar achieves over 90% precision in reference extraction through multi-source parsing, including PDFs and LaTeX when available [^crawling-sorc]. However, recent uploads may have indexing delays of 1 to 7 days, and version differences might not be distinguished.

**Limitations** The API may lack data for very new papers, non-English content, or unconventional formats. In such cases, cross-verify with the source files.

## Requirement

In this milestone, students are provided with a range of arXiv paper IDs by the Lab Instructors and scrape the papers in that range programmatically. As the discovery section frames it, the work is to resolve these assigned IDs and to locate every version of each paper, which is the graded part of the milestone rather than a harvest of arXiv at scale. For each assigned paper, **all available versions must be crawled**, including the initial submission and any subsequent revisions. arXiv version IDs follow the convention of appending the suffix `v`\<version number\> to the base ID, for example `2310.12345v1` or `2310.12345v2`, and for papers that were submitted once you should suffice it with `v1`. Each version is retrieved individually through the versioned `/src/` endpoint introduced above.

The scraping process should retrieve full-text source files, metadata, BibTeX references, and crawled reference information for each version, ensuring comprehensive coverage of the assigned papers. As the full size of each paper may be very large due to the size of contained figures, you are advised to **REMOVE any figure** from the scraped data as we are not going to need it (for your future work ;-)). Do the removal by extraction rather than by editing: extract only the `.tex` and `.bib` files from each source archive so that figure binaries and other non-source files never enter the corpus, and keep the LaTeX commands that define figures, such as `figure` environments and `\includegraphics` lines, untouched inside the TeX files, since Milestone 2 parses the document structure rather than the image binaries.

The reference metadata must additionally be crawled for each publication via the Semantic Scholar API. There is **no data submission** in this milestone: the corpus stays with the group as the working input of Milestones 2 and 3, and later becomes part of the final data submission on Hugging Face: the two tables of this milestone are specified below, and the later milestones add theirs in turn.

**Suggested data organization.** Groups organize their working data themselves. The following is a suggested convention to follow as-is or to adapt to whatever suits you best. Keep one working folder per publication, for example folder `2310-12345` for the ID `2310.12345`, holding the `.tex` and `.bib` files of every version and, for each version, its paper metadata and crawled reference metadata: title, authors, submission and revision dates, the venue when applicable, and for each crawled reference its title, authors, submission date, arXiv ID when one exists, and Semantic Scholar ID as returned by the API. Keep *all* crawled references locally, since at the final submission only the references carrying an arXiv ID become rows of the published `references` table, which keys on arXiv identifiers and serves as the matching pool of Milestone 3.

At the final submission in Milestone 3 the working data turns into the tables of the published dataset. This milestone already specifies two of them:

| **Table** | **Columns (types)** |
|:---|:---|
| papers | arxiv_id (string, non-null), title (string), authors (list of strings), submission_date (ISO string), revised_dates (list of strings), venue (string, nullable) |
| references | arxiv_id (string, non-null, the citing paper), ref_arxiv_id (string, non-null), ref_title (string), ref_authors (list of strings), ref_submission_date (string), ref_s2_id (string) |
*Dataset tables specified in this milestone, with one `references` row per crawled reference and its citing paper*

Milestone 2 mirrors this suggestion for the parsed and standardized data it produces, and the submission format of Milestone 3 lists all published tables side by side.

### Submission Format

#### Source Code

The group maintains a single public GitHub repository for the entire project: each milestone commits its code to it cumulatively, so the commit history documents the group's progress over time. The repository contains only source files such as Python files with the `.py` or `.ipynb` extensions and excludes data files, compiled executables, and other non-source materials, together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup and code execution
```

This milestone is submitted via Moodle as a group by pasting the public links to the shared code repository and to the milestone report described below. All the submissions above should be in the official language of your program. **NO late submission is permitted**.

#### Report Requirements (Jupyter Book)

The milestone report is a **Jupyter Book** maintained in a public repository of its own, separate from the shared code repository, and hosted on that repository's GitHub Pages. The book grows with the project: this milestone's report is its first section, and Milestone 2 adds a further section to the same book. The book must present the statistics and analysis of the scraped data, and its figures and tables must be *generated during book compilation*, not pasted as static screenshots, for quality and interactivity. The report should detail the implementation process, including how the scraping works, the tools and libraries used, for example the arXiv API, OAI-PMH, the Semantic Scholar API, and the `requests` library, and relevant statistics such as the number of papers scraped successfully, the overall success rate, the average paper size in bytes before and after removing figures, the average number of references per paper, and the average success rate for scraping reference metadata.

The scraper's performance should also be illustrated through two main points, running time and memory footprint. Running time counts the total time to process one paper, the average time to process each of the required papers, and the total time for entry discovery, while memory footprint counts the maximum RAM used during the scraping, the average RAM consumption, the maximum disk storage required, and the final output's storage size. Measure both points in an auditable way, for example peak RAM through `/usr/bin/time -v` or `psutil`, average RAM through periodic sampling, and disk usage through `du`. These tools are examples, not requirements. If the system consists of several programs, the runtime is counted as the wall time taken to run the system in an end-to-end way, while the memory footprint is considered as the total memory consumed by the full system. The testbed for the final benchmarking is a Google Colab instance running on CPU-only mode. No upper limit on the running time of the scraper is enforced, while the upper limit on maximum disk usage is given by the Colab instance.

The `README.md` of the repository stays separate: it provides clear instructions on setting up the necessary environment, such as the Python version and the packages to install through pip or conda, and running the code with specific configurations.

## Grading Criteria

Your grade is determined upon five main criteria as listed below:

- **Report (Jupyter Book):** Does the report illustrate sufficient information as previously mentioned, with figures and tables generated during book compilation?

- **Source Code:** Is the code clean, readable and runnable?

- **Discovery & Crawling:** Are the discovery and download methods used appropriately, with full version coverage of the assigned papers?

- **Resulted Data:** To what extent has the scraper successfully crawled, and how well does the corpus follow the suggested conventions?

- **Scraper's Performance:** How efficient is the scraper compared to others?

[^crawling-arxiv-api-manual]: arXiv.org. (2007). *arXiv API User’s Manual*. [https://info.arxiv.org/help/api/user-manual.html](https://info.arxiv.org/help/api/user-manual.html)

[^crawling-arxiv-api-basics]: arXiv.org. (2007). *arXiv API Basics*. [https://info.arxiv.org/help/api/basics.html](https://info.arxiv.org/help/api/basics.html)

[^crawling-arxiv-py-github]: Schwab, L. (2015). *arxiv.py: Python wrapper for the arXiv API*. GitHub, [https://github.com/lukasschwab/arxiv.py.](https://github.com/lukasschwab/arxiv.py.)

[^crawling-arxiv-api-tou]: arXiv.org. (1999). *Terms of Use for arXiv APIs*. [https://info.arxiv.org/help/api/tou.html](https://info.arxiv.org/help/api/tou.html)

[^crawling-oai-pmh-arxiv]: arXiv.org. (1999). *Open Archives Initiative (OAI) - arXiv info*. [https://info.arxiv.org/help/oa/index.html](https://info.arxiv.org/help/oa/index.html)

[^crawling-oai-pmh-cutover]: arXiv API Discussion. (2025). *OAI-PMH Endpoint cutover*. [https://groups.google.com/a/arxiv.org/g/api/c/4Cm8bc7A6JM](https://groups.google.com/a/arxiv.org/g/api/c/4Cm8bc7A6JM)

[^crawling-kaggle-arxiv]: Cornell University. (2025). *arXiv Dataset*. Kaggle, [https://www.kaggle.com/datasets/Cornell-University/arxiv.](https://www.kaggle.com/datasets/Cornell-University/arxiv.)

[^crawling-arxiv-html-paper]: Ginev, D., & others. (2024). HTML papers on arXiv – why it is important, and how we made it happen. *arXiv Preprint arXiv:2402.08954*.

[^crawling-arxiv-whytex]: arXiv.org. (1999). *Why Submit the TeX/LaTeX Source?* [https://info.arxiv.org/help/faq/whytex.html](https://info.arxiv.org/help/faq/whytex.html)

[^crawling-arxiv-mimetypes]: arXiv.org. (1999). *Media types - arXiv info*. [https://info.arxiv.org/help/mimetypes.html](https://info.arxiv.org/help/mimetypes.html)

[^crawling-arxiv-downloader]: Braun, S. (2023). *arxiv-downloader: Command-Line Tool for arXiv*. GitHub, [https://github.com/braun-steven/arxiv-downloader.](https://github.com/braun-steven/arxiv-downloader.)

[^crawling-arxiv-s3-bulk]: arXiv.org. (2009). *arXiv Bulk Data Access - Amazon S3*. [https://info.arxiv.org/help/bulk_data_s3.html](https://info.arxiv.org/help/bulk_data_s3.html)

[^crawling-semantic-scholar-api]: Allen Institute for AI. (2026). *Semantic Scholar Academic Graph API*. [https://api.semanticscholar.org/api-docs/](https://api.semanticscholar.org/api-docs/)

[^crawling-semantic-scholar-platform]: Kinney, R., Anastasiades, C., Authur, R., & others. (2023). The Semantic Scholar Open Data Platform. *arXiv Preprint arXiv:2301.10140*.

[^crawling-sorc]: Ammar, W., & others. (2018). The Semantic Scholar Open Research Corpus. *arXiv Preprint arXiv:1805.02234*.

---

<a id="milestone-parsing"></a>

## Project Milestone 2 — Hierarchical Parsing and Standardization

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/parsing/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/parsing-5ea96dd2b37a4dc5b36db8de0d231ea6.md)

## Objectives

In this milestone, students will transition from simple data collection to advanced data processing and analysis. The focus is to transform the unstructured raw data, the LaTeX sources crawled in Milestone 1, into a structured hierarchical format with cleaned, normalized, and deduplicated content. This practice mimics the real-world data science workflow of unstructured text processing and standardization. The machine learning part of this workflow, the reference matching pipeline, follows in Milestone 3 and consumes the outputs produced here.

## Description

Students are required to implement an automatic parser that processes the scraped LaTeX source files from the previous Milestone. The processing pipeline consists of the following components:

### Multi-file Gathering

The content of a LaTeX source is often spread across multiple `.tex` files, for example through the `\input` or `\include` commands. Students must programmatically identify the main compilation path and parse only those files that are actually included in the final PDF rendering. Unused or redundant files found in the source directory must be ignored. Concretely, the publication root is the `.tex` file containing the `\documentclass` declaration. Follow `\input` and `\include` commands transitively, treating commands that are commented out as plain text rather than includes, so the files reachable from the root form the compilation path and everything else in the source directory is a redundant auxiliary file. Following this path reproduces what LaTeX itself would compile, and the parse therefore covers what a reader of the final PDF sees.

### Hierarchy Construction

##### Hierarchy Structure

The goal is to convert the raw LaTeX code into a hierarchical tree structure for each version of each publication.

- The **Document** acts as the root.

- **Chapters** or **Sections** typically comprise the second level.

- Other elements such as **Subsections**, **Paragraphs**, and subsequent logical divisions form the lower levels. Since the exact nesting order depends on the publication's specific formatting, the parser is required to automatically identify the appropriate hierarchical level for each such element.

##### Parsing Notes

To ensure consistency, the parser must adhere to specific rules regarding element granularity and exclusion:

- **Smallest Elements:** The leaf nodes of the hierarchy must be **Sentences**, meaning text separated by dots or periods, **Block Formulas**, meaning mathematical blocks such as the contents of an `equation` environment or of `$$...$$`, and **Figures**, with **Tables** also considered a type of Figure for this purpose. The itemized points are considered as branching into deeper levels, meaning that a block of `\begin{itemize}...\end{itemize}` is considered as a higher component with each point being a next-level element. Sentence leaves carry the prose content of body text: do not split inside mathematics, commands, abbreviations such as i.e. and et al. and Fig. 1, URLs, or decimal numbers, since a dot that does not end a sentence does not create a new leaf.

- **Exclusions:** References sections should **not** be parsed into the hierarchy.

- **Inclusions:** Acknowledgements and Appendices, often unnumbered through the `\section*` form, **must** be included.

### Standardization and Deduplication

##### Cleanup and Normalization

Students must clean and normalize the data within the hierarchy:

- **LaTeX Cleanup:** Remove unnecessary formatting commands, such as `\centering`, the `[htpb]` placement option, and `\midrule`, that do not contribute to semantic meaning.

- **Math Normalization:** Convert all inline mathematics to a unified format such as the `$...$` form, and convert all block mathematics to a unified format such as the `\begin{equation}...\end{equation}` form.

##### Reference Extraction

For citations defined using `\bibitem` within the `.tex` files, students must convert them into standard BibTeX entries using programmatic tools such as regular expressions.

##### Deduplication

Deduplication is required at two levels, and both levels operate *across versions* of a publication:

- **Reference Entries:** Duplicated reference entries inside each version or across different versions of a single publication should be properly handled. If different citation keys, the entry names, refer to the same underlying reference content, a single citation key should be chosen, and the `\cite{}` commands of the remaining entries must be renamed to this chosen key. Additionally, the deduplication process should unionize the fields of the duplicate entries rather than selecting one entry while discarding all other information. Consider one reference that survives through three versions: version 1 lists it as `vaswani2017` with title, author, and year, version 2 renames it to `vit_transformer` and adds `doi`, and version 3 keeps the same reference as `vit_transformer` but drops `year`. The unified entry then keeps one chosen key, unions the fields into title, author, year, and doi, and the `\cite` commands pointing to the dropped keys are renamed to the chosen key, which is exactly the row that lands in the `bibtex` table below. A worked example of the other level follows with the tables in the Requirement, where one shared sentence serves both versions as a single element.

- **Full-text Content:** Full-text content deduplication must be applied to the hierarchical elements. If an element's text content matches exactly across different versions, a full-text match after cleanup, it should be represented by a single identifier in the final output, reducing redundancy. Note: full-text matching should be performed *after* cleanup to remove discrepancies in minor details such as formatting or spacing that might otherwise cause the code to identify identical texts as different.

## Requirement

Process every publication produced in Milestone 1. For each publication, parse every version's LaTeX source, following the compilation path, build the hierarchical structure, standardize and deduplicate the content, and extract the references into a unified set of BibTeX entries. A version without TeX sources, kept as an empty record by Milestone 1, yields no parsed elements: record the version as empty rather than skipping it, so coverage statistics and the tables below reflect reality.

There is **no data submission** in this milestone: the processed corpus stays with the group as the working input of Milestone 3, just as the crawled corpus does in Milestone 1.

**Suggested data organization.** As in Milestone 1, groups organize their working data themselves. This suggestion adapts the same spirit to the parsed and standardized data, so follow it as-is or adapt it for convenience. For each publication, keep the parsed content and structure of *all* versions together: the parsed elements, the per-version parent relations between them, and the unified, deduplicated BibTeX entries. This replaces the raw TeX folder from Milestone 1 as the downstream material, so keep enough to assemble the final tables without re-parsing.

At the final submission in Milestone 3 this data turns into the tables of the published dataset. This milestone already specifies three of them:

| **Table** | **Columns (types) and contents** |
|:---|:---|
| elements | one row per *distinct* element across all versions of the publication: element_id (string, non-null), arxiv_id (string, non-null), kind (string, dictionary), content (string). Content that matches exactly across versions, a full-text match after cleanup, occupies a single row |
| hierarchy | arxiv_id (string, non-null), version (int), element_id (string, non-null), parent_id (string, non-null), with one row per node-parent edge of each version |
| bibtex | arxiv_id (string, non-null), citation_key (string, non-null), entry_type (string, dictionary), title (string), authors (list of strings), year (int, nullable), doi (string), journal (string), url (string), holding the unified BibTeX entries after deduplication and merging |
*Dataset tables specified in this milestone*

**How the elements and the hierarchy store across versions.** The elements of different versions share one store: when a leaf or component appears in two versions with identical cleaned content, it is recorded once, so a single `element_id` serves both versions, which is exactly the deduplication required above. The `hierarchy` rows then hold only the node-parent edges of each version, and an element contributed by an earlier version may act as a node in a later version's edges, attached to a parent that exists only in that later version. Element IDs begin with the publication key followed by a discriminant that is unique inside the publication. The miniature example below, one publication with two versions and one sentence unchanged across both, shows the resulting rows:

| **element_id**   | **kind** | **content**                            |
|:-----------------|:---------|:---------------------------------------|
| 2310-12345#root1 | document | Version 1 root                         |
| 2310-12345#root2 | document | Version 2 root                         |
| 2310-12345#h1    | heading  | Introduction                           |
| 2310-12345#h2    | heading  | Background and model                   |
| 2310-12345#s1    | sentence | We study the citation matching problem |
*Example `elements` rows, one shared store where `s1` serves both versions*

| **version** | **element_id** | **parent_id**    |
|:------------|:---------------|:-----------------|
| 1           | 2310-12345#h1  | 2310-12345#root1 |
| 1           | 2310-12345#s1  | 2310-12345#h1    |
| 2           | 2310-12345#h2  | 2310-12345#root2 |
| 2           | 2310-12345#s1  | 2310-12345#h2    |
*Example `hierarchy` rows: the shared sentence `s1` is a node in both versions, attached to `h1` in version 1 and to `h2` in version 2*

## Submission Format

### Source Code

This milestone's code is committed to the same single public GitHub repository used in Milestone 1, continuing the cumulative history that documents the group's progress. The repository contains only source files such as Python files with the `.py` or `.ipynb` extensions and excludes data files, compiled executables, and other non-source materials, together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup and code execution
```

This milestone is submitted via Moodle as a group by pasting the public links to the shared code repository and to the milestone report described below. All the submissions above should be in the official language of your program. **NO late submission is permitted**.

### Report Requirements (Jupyter Book)

Students must prepare a milestone report compiled as a **Jupyter Book**, the same book repository introduced in Milestone 1 and hosted on its GitHub Pages, adding a parsing-and-standardization section to that book rather than creating a new one. The book must present the statistics and analysis of the processed data, and its figures and tables must be *generated during book compilation*, not pasted as static screenshots, for quality and interactivity. The report should specifically cover:

- **Hierarchical Parsing:** Explanation of the logic used to detect file structure, parse the LaTeX hierarchy, and handle multi-file inputs.

- **Standardization:** Details on how data cleaning, math normalization, and reference deduplication were implemented.

- **Statistics:** Relevant statistics such as the parsing success rate, the version coverage of every publication, and the element/entry counts before and after deduplication.

The parser's performance should also be illustrated through two main points, running time and memory footprint: running time counts the end-to-end wall time of the parser and the average time to process one publication, while memory footprint counts the maximum RAM used and the final output's storage size. The testbed for the final benchmarking is a Google Colab instance running on CPU-only mode. No upper limit on the running time is enforced, while the upper limit on maximum disk usage is given by the Colab instance.

The `README.md` of the repository stays separate: it provides clear instructions on setting up the necessary environment, such as the Python version and the packages to install through pip or conda, and running the code with specific configurations.

## Grading Criteria

Your grade is determined upon five main criteria as listed below:

- **Hierarchical Parser:** Accuracy of the parser in detecting structure, handling multi-file sources, and identifying the appropriate hierarchical levels.

- **Standardization & Deduplication:** Correct cleanup, math normalization, reference extraction, and both deduplication levels, covering reference entries through `\cite` renaming and field unionization as well as full-text content across versions.

- **Parser's Performance:** How efficient the parser is through running time and memory footprint.

- **Code Quality & Reproducibility:** Clean, runnable code with clear instructions.

- **Report (Jupyter Book):** Figures generated at book compilation, interactivity, and clarity of the hosted book.

---

<a id="milestone-matching"></a>

## Project Milestone 3 — Reference Matching Pipeline

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/matching/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/matching-06eeb42f80468333de4ce91f69ff4dfa.md)

## Objectives

In this milestone, students will apply machine learning techniques to a real matching problem: the citation entries extracted from the parsed text are linked with their external metadata. Concretely, the BibTeX entries produced in Milestone 2 must be matched to the correct arXiv IDs among the reference metadata crawled in Milestone 1 via the Semantic Scholar API [^matching-semantic-scholar-api][^matching-semantic-scholar-platform]. This practice mimics the real-world data science workflow of entity resolution with unstructured text processing, standardization, feature engineering, and matching algorithms assembled into a complete pipeline.

## Description

Students must perform a matching task between the standardized BibTeX entries of Milestone 2, whose unified form is the `bibtex` table described there, and the crawled reference metadata of the same publications, the `references` table described in Milestone 1. The goal is to identify, for each extracted BibTeX entry, the arXiv-keyed reference it corresponds to. The full data science pipeline is described below.

### Data Cleaning

Perform any additional text preprocessing required to facilitate the matching process, with steps such as lowercasing, stop-word removal, or specific tokenization for author names and titles.

### Data Labelling

Students need to create a ground truth dataset by labelling associations between the extracted BibTeX entries and the crawled references of each publication. The task is to identify, for each BibTeX entry, the reference it corresponds to: a single correct association per entry, and none when no crawled reference matches. Pairs exist inside a publication only, so an association pairs one entry with one reference of the same publication. Students are required to:

- Manually label references for at least **5 publications**. Each manually-labeled publication must have at least **20 labeled BibTeX entries**, its quantity $Q$, with at least 100 labeled entries across the pool.

- Implement automatic matching with classic tools such as regex or string similarity heuristics and label at least **10%** of the publications outside the manual pool. The automatic matcher labels every BibTeX entry of the publications it is applied to.

Labeled entries define the ground truth for training and evaluation: for each labeled entry, its row in the candidate matrix of the Data Modeling section is completed, one positive when a true reference exists and an all-negative row otherwise. The internal format for these labels is up to the students but must be clearly documented in the group's repository and presented in the poster.

### Feature Engineering

Students must first frame the matching task as a specific supervised learning problem such as classification, regression, recommendation, or ranking, which determines the input format such as entry-reference pairs, triplets, or candidate lists. Based on this chosen input format, students must perform feature engineering to construct reasonable features for the model. These features can range from simple string matching scores or embeddings to complex statistical features.

Students must justify the creation of each feature in the poster and the repository documentation, explaining the underlying idea. This insight and idea should be illustrated with appropriate data analysis.

**Note:** In this feature engineering phase, students are allowed to construct features based on hierarchies previously formed in Milestone 2.

### Data Modeling

The target of this problem is to match the BibTeX entries standardized in Milestone 2 with the associated references in the crawled metadata of the same publication.

If a publication has $m$ BibTeX entries and $n$ crawled references with arXiv IDs, its candidate space is an $m \times n$ binary matrix: row $i$ holds BibTeX entry $i$, column $j$ holds reference $j$, and cell $(i, j)$ carries a binary label that reads **yes** when entry $i$ corresponds to reference $j$ and **no** otherwise. Labeling is scoped to publications: the pools selected under Data Labelling contribute the labeled publications, and each labeled publication's matrix is completed *row-wise*, so every labeled entry carries exactly one yes cell holding its true reference when one exists while the remaining cells of its row are no. An entry with no true reference among the crawled references makes an entirely no-valued row. Unlabeled entries simply carry no rows.

The data split strategy is as follows:

- **Test Set:** Includes 1 publication from the manually labeled set and 1 publication from the automatically matched set.

- **Validation Set:** Includes 1 publication from the manually labeled set and 1 publication from the automatically matched set.

- **Training Set:** Consists of all remaining publications (the remaining manually labeled ones and the remaining automatically matched ones).

### Model Evaluation

Evaluate the trained model on the **Test set**, comprising the two publications defined above. For every labeled BibTeX entry, the model outputs a ranked list of the **top 5 candidate references**. Post-processing of the results is allowed.

The evaluation metric is **Mean Reciprocal Rank @5, written MRR@5**.

$$\text{MRR@5} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$

where $|Q|$ is the number of labeled BibTeX entries in the Test set, the same quantity $Q$ as in Data Labelling, and $\text{rank}_i$ is the position of the correct reference among the top-5 candidates of the $i$-th entry. If the correct reference does not appear among the five candidates, the score of that entry is **zero**.

## Requirement

Perform the full pipeline, covering cleaning, labelling, feature engineering, modeling, and evaluation, on the assigned publications. The matching results are published in the `predictions` table of the final Hugging Face dataset, specified in the Submission Format section. The table contains one row per BibTeX entry of each publication:

| **Column** | **Type** | **Content** |
|:---|:---|:---|
| arxiv_id | string, non-null | Publication the entry belongs to |
| partition | string, dictionary | `train`, `valid`, or `test` |
| citation_key | string, non-null | BibTeX entry name, its identifier |
| groundtruth_arxiv_id | string, nullable | The correct arXiv ID of the entry's true reference, when known |
| cand_1 to cand_5 | string, nullable | The model's ranked top-5 candidates: cand_1 best, cand_5 last |
*Columns of the predictions table*

**Important Note:** Only the publications that are used for the reference matching task, namely those in the Training, Validation, and Test sets, have rows in this table.

## Submission Format

### Final Data Submission (Hugging Face)

There is **no intermediate data submission** in this project. The final data submission happens in this milestone: the fully processed data is hosted as a public **Hugging Face dataset**, following the hosting instructions given by the Lab Instructors, and the dataset link is pasted via Moodle.

**Storage format: Parquet.** Publish the processed corpus as *sharded Parquet*, the Hub's standard dataset format which the viewer and the streaming backend read directly, in six tables with one unified, explicit schema. Keep the columns flat and primitive: one-level string lists for authors and revised dates are fine, while nested objects and serialized JSON blobs are not.

Milestones 1 and 2 already specified five of these tables beside the data they produce, and the predictions table below completes the set:

| **Table** | **Content** | **Described in** |
|:---|:---|:---|
| papers | the crawled paper metadata | Milestone 1 |
| references | the crawled reference metadata with one row per crawled reference and its citing paper, keeping the arXiv-keyed references only | Milestone 1 |
| elements | the parsed elements of all versions, deduplicated into one store | Milestone 2 |
| hierarchy | the per-version node-parent edges between elements | Milestone 2 |
| bibtex | the unified BibTeX entries after deduplication | Milestone 2 |
| predictions | the matching results with columns given below | this milestone |
*Tables of the published dataset and where their column specs live*

The dataset repository itself is simple:

    └── <dataset-repo>/
        ├── README.md
        └── data/
            ├── papers/
            ├── references/
            ├── elements/
            ├── hierarchy/
            ├── bibtex/
            └── predictions/

At the root, a **dataset card**, a `README.md` with YAML metadata, tells the Hub how the tables map to files:

**Dataset card metadata (README.md):**

```
---
configs:
- config_name: papers
  data_files:
  - split: train
    path: data/papers/*.parquet
- config_name: references
  data_files:
  - split: train
    path: data/references/*.parquet
- ...one config per table...
---
```

The working organization between milestones is up to each group, and Milestones 1 and 2 suggest what information to keep, since these tables are only the publishing format for the final submission. Avoid custom loading scripts: the filename patterns and the card above are all the Hub needs. **NO late submission is permitted**.

### Source Code

This milestone's code is committed to the same single public GitHub repository used in Milestones 1 and 2, continuing the cumulative history that documents the group's progress. The repository contains only source files such as Python files with the `.py` or `.ipynb` extensions and excludes data files, compiled executables, and other non-source materials, together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup, code execution, feature and label documentation
```

This milestone is submitted via Moodle as a group: the poster file (see below) and the public links to the Hugging Face dataset and to the shared code repository. All the submissions above should be in the official language of your program.

### Poster and Poster Session

The final grading format is a **poster session**. Each group submits **one pptx file containing a single-page poster** in the form factor of **portrait A2** for review. The poster should present the group's selected pieces of work: those representing the *highest quality*, the *most outstanding* results, and the work the group believes makes it *distinct from the others*. Examples include the engineered features with their justification and analysis, the model and its MRR results, and notable statistics of the parsing and matching pipeline.

Upon acceptance of the review, the group **prints the poster** and **presents it at the final poster session**.

## Grading Criteria

Your grade is determined upon five main criteria as listed below:

- **ML Pipeline Implementation:** Correct implementation of cleaning, labeling, feature engineering, and modeling steps for reference matching.

- **Evaluation & Analysis:** Proper use of MRR, clear justification of features, and insightful analysis of the results, as presented in the poster and the repository documentation. Note that students using external-knowledge methods such as LLMs or pretrained models shall be judged in separation from the other students.

- **Dataset Schema:** The published Parquet dataset conforms to the table and column specification, ready for streaming.

- **Code Quality & Reproducibility:** Clean, runnable code with clear instructions.

- **Poster & Session:** Quality of the selected work, the single-page portrait A2 poster, and the poster session presentation.

[^matching-semantic-scholar-api]: Allen Institute for AI. (2026). *Semantic Scholar Academic Graph API*. [https://api.semanticscholar.org/api-docs/](https://api.semanticscholar.org/api-docs/)

[^matching-semantic-scholar-platform]: Kinney, R., Anastasiades, C., Authur, R., & others. (2023). The Semantic Scholar Open Data Platform. *arXiv Preprint arXiv:2301.10140*.
