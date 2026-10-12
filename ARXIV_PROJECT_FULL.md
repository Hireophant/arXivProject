# arXiv Project — Toàn bộ đề bài và các milestone

Nguồn: https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/  
Ngày tải: 11/10/2026 (Asia/Bangkok).

Tài liệu này gộp các bản Markdown tải trực tiếp từ website môn học: trang tổng quan và cả ba milestone. Giữ nguyên nội dung tiếng Anh, ví dụ code, công thức, bảng, quy định và tiêu chí chấm điểm. Tiêu đề được điều chỉnh cấp để tiện đọc; liên kết MyST và trích dẫn được chuyển sang Markdown. Các trang tài liệu bên ngoài được giữ dưới dạng liên kết tham khảo.

## Mục lục

1. [Đề bài tổng quan](#project-overview)
2. [Milestone 1 — Data Crawling](#milestone-crawling)
3. [Milestone 2 — Hierarchical Parsing and Standardization](#milestone-parsing)
4. [Milestone 3 — Reference Matching Pipeline](#milestone-matching)

---

<a id="project-overview"></a>

## arXiv Project — Problem Statements

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/index-2375bae5ef60f111c05ba4e8ee810962.md)

### Logistics

The project is a **group work**. Each milestone is submitted as a group via Moodle:

- **Shared code repository** — one public code repository per group serves the whole project: each milestone's code is committed to it cumulatively, so the commit history documents the group's progress. Milestones 1 and 2 paste its link via Moodle together with the report link; Milestone 3 submits it together with the poster and the dataset.
- **Jupyter Book (Milestones 1 and 2)** — the milestone reports form one public **Jupyter Book**, hosted on its own separate repository's GitHub Pages: Milestone 1's report is the book's first section and Milestone 2 adds the next section. Report figures and tables must be generated during book compilation.
- **Final data submission** — there is no intermediate data submission. The fully processed data is hosted as a **Hugging Face dataset** of sharded Parquet tables, following the Milestone 3 schema and the hosting instructions given by the Lab Instructors, and the dataset link is submitted via Moodle.
- **Final grading** — a **poster session**. Each group submits one pptx file containing a single-page poster in the form factor of **portrait A2** for review; upon acceptance, the group prints the poster and presents it at the poster session.

### Milestones

- **[Project Milestone 1 — Data Crawling](#milestone-crawling)** — build the raw corpus: discover the assigned arXiv papers in the range provided by the Lab Instructors, crawl every version of each publication (full-text LaTeX sources, metadata, and reference metadata), and analyze the scraped corpus.
- **[Project Milestone 2 — Hierarchical Parsing and Standardization](#milestone-parsing)** — structure the corpus: parse each version into a hierarchical tree, standardize the content, convert `\bibitem` references into BibTeX, deduplicate across versions, and analyze the processed data.
- **[Project Milestone 3 — Reference Matching Pipeline](#milestone-matching)** — run the machine learning pipeline: clean, label, engineer features, model, and evaluate a reference-matching system scored with Mean Reciprocal Rank (MRR).

Milestone-specific requirements and submission formats are detailed in each milestone page.

### Regulations

Ensure your code is well-documented with clear comments. You can use online documents for reference, but you must provide complete citations. You are free to discuss your topics with classmates, but your work must be implemented and interpreted according to your own understanding.

**Any milestone will be graded zero if there is any dishonest behaviour detected.**

---

<a id="milestone-crawling"></a>

## Project Milestone 1 — Data Crawling

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/crawling/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/crawling-1316f8d7fe5407ee986f06e887471c80.md)

## Objectives

In this milestone, students will employ the knowledge about data scraping (or crawling) obtained from the theoretical lectures to scrape an online repository. This practice is expected to help you convert that knowledge into useful skills about the engineering aspect of your data science journey. However, do not think that this milestone, as well as the others, will cover all the necessary skills you should know before joining realistic projects—you must continue learning even after the completion of this course!

This year's target is arXiv, the open-access repository of more than two million papers. Scraping arXiv is already a known practice in data engineering courses, though most of them exclusively focus on metadata rather than the full-text resources. Here, you will get ahead of them by collecting the **full-text LaTeX sources** of the papers rather than the hard-to-process PDFs. The corpus built in this milestone is the working foundation for the parsing and machine learning work of Milestones 2 and 3, so make the crawl complete and correctly organized.

## Description

This milestone consists of three main areas: discovering paper entries, downloading their full-text source files, and extracting structured reference information.

### Entry Discovery

The first step in any arXiv crawling workflow is to identify which papers you want to collect. This section introduces three common discovery methods that are used in practice to find relevant paper entries efficiently.

#### arXiv API for Targeted Discovery

The arXiv API (<http://export.arxiv.org/api/query>) provides an HTTP interface for retrieving information on papers based on search keywords, authors, or categories. It returns results in Atom XML format, which can be parsed programmatically. This method is particularly convenient for targeted queries or daily updates of new submissions.

**Key Parameters and Usage** The arXiv API accepts several useful parameters:

- `search_query`: Field-specific search (for instance `ti:neural AND cat:cs.AI`)

- `id_list`: Comma-separated arXiv IDs for direct lookup

- `start`, `max_results`: For pagination control

- `sortBy`, `sortOrder`: Sorting criteria such as submission date

The library `arxiv.py` allows flexible interaction with this API [^crawling-arxiv-api-manual][^crawling-arxiv-api-basics][^crawling-arxiv-py-github]. Two practical notes for this year: the API etiquette asks for modest request rates—wait at least 3 seconds between successive calls, on one connection at a time [^crawling-arxiv-api-tou] (the client used below enforces this delay automatically); and `arxiv.py` went through breaking changes in its 2.x–4.x releases (2025–2026), where the old patterns `search.results()` and `Result.download_pdf()` / `Result.download_source()` were removed in version 4.0.0 (May 2026)—always use the modern `client.results(search)` style and consult the library's README for the current behavior.

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

Results are returned as structured objects containing metadata such as title, authors, abstract, and arXiv ID.

#### OAI-PMH for Metadata Harvesting

The Open Archives Initiative Protocol for Metadata Harvesting (OAI-PMH) enables systematic retrieval of metadata from arXiv. It is the officially supported bulk-access protocol for academic repositories and is well suited for automated metadata gathering. Since March 2025 the arXiv endpoint lives at <https://oaipmh.arxiv.org/oai>; the old address `export.arxiv.org/oai2` was retired during arXiv's cloud migration and may only redirect, so point new harvesters at the new endpoint [^crawling-oai-pmh-arxiv][^crawling-oai-pmh-cutover].

**Main Concepts** OAI-PMH uses a set of "verbs" (commands) to request data from the repository:

- `Identify`: Get information about the repository

- `ListRecords`: Retrieve multiple records including metadata

- `ListIdentifiers`: Retrieve identifiers (IDs) only

**Selective Harvesting** Harvests can be scoped by date range (`from`/`until`), by category (e.g., `set=cs`), and by metadata format—the `arXiv` prefix is recommended. One behavioral change of the March 2025 rewrite matters in practice: resumption tokens no longer encode the collection size and *expire daily*, so design a full sweep to finish within a day or to resume gracefully from saved state. The same 3-second pacing applies here as well.

**Basic OAI-PMH retrieval function (endpoint updated March 2025):**

```
from sickle import Sickle

def harvest_arxiv_records(date_from, date_to):
    sickle = Sickle("https://oaipmh.arxiv.org/oai")
    records = sickle.ListRecords(metadataPrefix='arXiv',
                                 from_=date_from, until=date_to)
    return [r.metadata for r in records]
```

This example shows how to obtain a structured list of metadata dictionaries that can later be stored as JSON or a database. Resumption tokens handle pagination automatically—harvests of thousands of records run without manual page management, and for large time-bounded sweeps the protocol far outpaces the API [^crawling-oai-pmh-arxiv].

#### Kaggle Dataset for Pre-Aggregated Metadata

The Cornell arXiv dataset available on Kaggle (<https://www.kaggle.com/datasets/Cornell-University/arxiv>) provides pre-collected metadata for over 1.7 million papers. It can be used directly without any API calls and is ideal for local data processing or exploratory searches [^crawling-kaggle-arxiv].

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

Once you have identified the list of papers to collect, the next step is to obtain their full source files. The goal here is to retrieve the original submission TeX sources, either archived in `.tar.gz` format or in other forms, without modifying their contents. Note that there are many types of sources other than `.tar.gz`, and you will need to identify which types contain the `.tex` or `.bib` files in order to include them in the working corpus. Other forms such as PDF files or `.docx` Word documents may not be convertible into TeX files; for such versions, keep an empty record in the corpus rather than dropping the publication.

arXiv provides source files for approximately 97% of its submissions—the rest arrive as PDF-only [^crawling-arxiv-html-paper][^crawling-arxiv-whytex]. A source archive is a gzipped tar containing the `.tex` files (often several, linked via `\input` or `\include`), `.bib` bibliography files, style and class files, occasionally a pre-compiled `.bbl`, and the figure binaries. Source archives are served by the dedicated mirror `export.arxiv.org`: the preferred endpoint `https://export.arxiv.org/src/{arxiv_id}` consistently returns a gzipped tar archive, and it also accepts *versioned* identifiers (e.g., `.../src/2310.12345v2`), which is how every revision of a publication is retrieved individually [^crawling-arxiv-mimetypes]. Point automated downloads at this mirror and never at the main site `arxiv.org` (aggressive crawling there triggers automatic robot detection and 403 blocks), and use a descriptive User-Agent header with the same 3-second pacing.

#### arXiv API Download Using Python

The simplest and most common way to download a paper's full source archive is through the `arxiv.py` Python library, which wraps the API into user-friendly methods.

**Basic Workflow**

1.  Query the API with the paper's arXiv ID to retrieve its metadata.

2.  Download the source archive from the `/src/` endpoint, using the versioned ID for a specific revision—arxiv.py 4.x no longer ships a download method, so fetch the archive yourself (e.g., with `urllib`) [^crawling-arxiv-py-github].

3.  Save the archive into the version's directory.

**Downloading an arXiv source file with arxiv.py (4.x):**

```
import arxiv
import urllib.request

def get_source(arxiv_id, save_dir="./sources"):
    paper = next(arxiv.Client()
                     .results(arxiv.Search(id_list=[arxiv_id])))
    print(paper.title)
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

The flag `-s` ensures that source files are fetched (not PDFs), and `-d` designates the output directory.

#### Amazon S3 Bulk Repository Access

arXiv maintains complete source archives within an Amazon Web Services (AWS) S3 requester-pays bucket at `s3://arxiv/src/`. This interface is intended for large-scale retrieval, allowing structured downloads of `.tar` bundles containing multiple monthly paper packages [^crawling-arxiv-s3-bulk].

**Setup and Example Command** Before downloading, configure AWS credentials with `aws configure`. Then use:

```
aws s3 cp s3://arxiv/src/arXiv_src_2401_001.tar \
              ./bulk/ --request-payer requester
```

Each archive contains multiple submission source files grouped by upload date. The monthly chunks follow the naming pattern `arXiv_src_YYMM_NNN.tar`, and the complete archive is on the order of several TB and growing, so consult `arXiv_src_manifest.xml` for the exact chunk list before downloading. You can loop this process to download archives for consecutive months as needed. Alternatively, `s3cmd` provides a lightweight interface: `s3cmd get --recursive --requester-pays s3://arxiv/src/` retrieves all available source archives without manual iteration. (A free mirror of the same sources exists on Google Cloud Storage at `gs://arxiv-dataset`.)

#### Kaggle Mirror for Public Access

The Cornell arXiv dataset on Kaggle (<https://www.kaggle.com/datasets/Cornell-University/arxiv>) provides a mirror containing metadata entries referencing original arXiv source URLs. While the dataset itself does not contain full-texts, it can be utilized to automate requests for downloading original sources through the `/src/` endpoint.

**Integration Example** The below minimal code demonstrates how to read the Kaggle dataset and queue download requests for the corresponding arXiv IDs:

**Queueing source downloads using Kaggle metadata:**

```
import pandas as pd

def queue_sources_from_kaggle(metadata_file):
    data = pd.read_json(metadata_file, lines=True)
    ids = data['id'].dropna().head(3)  # first three IDs
    for arxiv_id in ids:
        print(f"Prepare download for {arxiv_id}")
```

This metadata-driven approach can serve as a scheduling mechanism before making individual API download calls.

#### Summary

| **Method**    | **Access Interface**   | **Example Tool**  |
|:--------------|:-----------------------|:------------------|
| arXiv API     | REST via Python client | arxiv.py          |
| Command-Line  | CLI utility            | arxiv-downloader  |
| Amazon S3     | Bulk cloud storage     | awscli or s3cmd   |
| Kaggle Mirror | Pre-collected metadata | pandas + API call |
*Available methods for retrieving arXiv source files*

### Extracting References

When working with arXiv papers, extracting structured reference information is essential for understanding citation relationships. This section introduces the Semantic Scholar API as a method to retrieve references and associated identifiers like arXiv IDs without direct LaTeX parsing.

#### Semantic Scholar

Semantic Scholar, developed by the Allen Institute for AI, indexes over 214 million papers and provides structured access to citation data through a free API [^crawling-semantic-scholar-api][^crawling-semantic-scholar-platform]. It excels in linking arXiv papers to broader academic graphs, offering fields such as titles, authors, years, and external identifiers. The API endpoint is `https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}`, where queries use the arXiv prefix for identification.

**Request Fields and Response** To obtain references, specify fields like `references`, `references.externalIds`, `references.title`, and `references.year` in the query parameters. The response is a JSON object containing an array of references, each with potential arXiv IDs in the `externalIds.ArXiv` field. A simple function to query and extract basic reference data is shown below:

**Querying Semantic Scholar for references:**

```
import requests

def get_paper_references(arxiv_id):
    url = f"https://api.semanticscholar.org/graph/v1/paper/arXiv:{arxiv_id}"
    params = {"fields": "references, references.externalIds, references.title"}
    response = requests.get(url, params=params)
    data = response.json()
    return data.get("references", [])
```

This retrieves the list of references for a given arXiv ID.

#### Extracting arXiv Identifiers

From the API response, arXiv IDs are found in the `externalIds` dictionary of each reference. The process involves iterating over the references array and checking for the presence of the `ArXiv` key.

**Handling Problematic Identifiers** Not every reference includes an arXiv ID, as some cite journal articles, books, or non-arXiv sources. Coverage is higher in fields like computer science, where arXiv is prevalent. Besides that, references published on arXiv before 2007 also possess a different scheme of indexing (the old `archive/YYMMNNN` format, e.g., `hep-th/9901001`), thus students should retain the original identifiers for such publications.

#### Rate Limits and Usage

The API enforces limits of 1 request per second and 100 requests per 5-minute window for unauthenticated use [^crawling-semantic-scholar-api]. Exceeding these triggers 429 errors, so implement delays and error handling. API key usage is permitted and will help you improve the runtime performance: the free tier shares one unauthenticated request pool that is subject to throttling during heavy use, while a (free) API key guarantees a steady 1 request/second, with higher limits available upon review.

**Accuracy Considerations** Semantic Scholar achieves over 90% precision in reference extraction through multi-source parsing, including PDFs and LaTeX when available [^crawling-sorc]. However, recent uploads may have indexing delays of 1 to 7 days, and version differences might not be distinguished.

**Limitations** The API may lack data for very new papers, non-English content, or unconventional formats. In such cases, cross-verify with the source files.

## Requirement

In this milestone, students are provided with a range of arXiv paper IDs by the Lab Instructors and scrape the papers in that range programmatically. For each assigned paper, **all available versions must be crawled**, including the initial submission and any subsequent revisions. arXiv version IDs follow the convention of appending a suffix "v\<version number\>" to the base ID (e.g., "2310.12345v1", "2310.12345v2"), and for papers that were submitted once you should suffice it with "v1". Each version is retrieved individually through the versioned `/src/` endpoint introduced above.

The scraping process should retrieve full-text source files (TeX), metadata, BibTeX references, and crawled reference information for each version, ensuring comprehensive coverage of the assigned papers. As the full size of each paper may be very large due to the size of contained figures, you are advised to **REMOVE any figure** from the scraped papers as we are not going to need it (for your future work ;-))—keep only `.tex`, `.bib`, and other text-based source files, and keep the LaTeX commands defining figures (e.g., `figure` environments) untouched, since Milestone 2 parses the document structure rather than the image binaries.

The reference metadata must additionally be crawled for each publication via the Semantic Scholar API. There is **no data submission** in this milestone: the corpus stays with the group as the working input of Milestones 2 and 3, and later becomes part of the final data submission on Hugging Face (format in Milestone 3).

**Suggested convention.** The following working convention is suggested—follow it as-is or adapt it to whatever suits your group best. Keep one working folder per publication, named after the arXiv ID in the "yymm-id" format (e.g., "2310-12345" for ID "2310.12345"), containing the versioned TeX sources (kept separated by version, e.g., `v1/`, `v2/`, ..., with the `.bib` files as they appear in the original sources—papers citing through `\bibitem` simply have none) together with:

- **metadata.json**: stores the paper's metadata, including at minimum: the paper title (as a string), authors (as a list of strings), submission date (as a string in ISO format), and revised dates (as a list of date strings in ISO format). Additionally, include the publication venue (e.g., journal or conference name) if applicable.

- **references.json**: contains a dictionary where keys are arXiv IDs (in "yymm-id" format) of the crawled references, and values are their respective metadata dictionaries. Each metadata dictionary should include at minimum: the reference paper title (as a string), authors (as a list of strings), submission date (as a string in ISO format), and Semantic Scholar ID (as provided by the Semantic Scholar API). Papers that do not have associated arXiv IDs are not put in this file, as the IDs serve as keys.

### Submission Format

#### Source Code

The group maintains a single public GitHub repository for the entire project: each milestone commits its code to it cumulatively, so the commit history documents the group's progress over time. The repository contains only source files such as Python files (`.py` or `.ipynb`)—excluding data files, compiled executables, or any other non-source materials—together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup and code execution
```

This milestone is submitted via Moodle as a group by pasting the public links to the shared code repository and to the milestone report (see below). All the submissions above should be in the official language of your program. **NO late submission is permitted**.

#### Report Requirements (Jupyter Book)

The milestone report is a **Jupyter Book** maintained in a public repository of its own—separate from the shared code repository—and hosted on that repository's GitHub Pages. The book grows with the project: this milestone's report is its first section, and Milestone 2 adds a further section to the same book. The book must present the statistics and analysis of the scraped data, and its figures and tables must be *generated during book compilation* (not pasted as static screenshots) for quality and interactivity. The report should detail the implementation process, including how the scraping works, the tools and libraries used (e.g., arXiv API, OAI-PMH, Semantic Scholar API, `requests` library), and relevant statistics such as: the number of papers scraped successfully, the overall success rate, the average paper size in bytes before and after removing figures, the average number of references per paper, and the average success rate for scraping reference metadata.

The scraper's performance should also be illustrated through two main points: running time (such as the total time to process one paper, the average time to process each of the required papers, the total time for entry discovery, etc.) and memory footprint (such as the maximum RAM used during the scraping, the average RAM consumption, the maximum disk storage required, the final output's storage size, etc.). If the system consists of several programs, the runtime is counted as the wall time taken to run the system in an end-to-end way, while the memory footprint is considered as the total memory consumed by the full system. The testbed for the final benchmarking is a Google Colab instance running on CPU-only mode. No upper limit on the running time of the scraper is enforced, while the upper limit on maximum disk usage is given by the Colab instance.

The `README.md` of the repository stays separate: it provides clear instructions on setting up the necessary environment (e.g., Python version, required packages via pip or conda) and running the code with specific configurations.

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

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/parsing/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/parsing-a67413221a4e5b2e3efec23d48f55237.md)

## Objectives

In this milestone, students will transition from simple data collection to advanced data processing and analysis. The focus is to transform the unstructured raw data—the LaTeX sources crawled in Milestone 1—into a structured hierarchical format with cleaned, normalized, and deduplicated content. This practice mimics the real-world data science workflow of unstructured text processing and standardization; the machine learning part of this workflow (the reference matching pipeline) follows in Milestone 3 and consumes the outputs produced here.

## Description

Students are required to implement an automatic parser that processes the scraped LaTeX source files from the previous Milestone. The processing pipeline consists of the following components:

### Multi-file Gathering

The content of a LaTeX source is often spread across multiple `.tex` files (e.g., using `\input` or `\include`). Students must programmatically identify the main compilation path and parse only those files that are actually included in the final PDF rendering. Unused or redundant files found in the source directory must be ignored.

### Hierarchy Construction

##### Hierarchy Structure

The goal is to convert the raw LaTeX code into a hierarchical tree structure for each version of each publication.

- The **Document** acts as the root.

- **Chapters** or **Sections** typically comprise the second level.

- Other elements such as **Subsections**, **Paragraphs**, and subsequent logical divisions form the lower levels. Since the exact nesting order depends on the publication's specific formatting, the parser is required to automatically identify the appropriate hierarchical level for each such element.

##### Parsing Notes

To ensure consistency, the parser must adhere to specific rules regarding element granularity and exclusion:

- **Smallest Elements:** The leaf nodes (smallest elements) of the hierarchy must be **Sentences** (separated by dots/periods), **Block Formulas** (mathematical blocks such as contents within `equation` environments or `$$...$$`), and **Figures** (note that **Tables** are also considered a type of Figure for this purpose). The itemized points are considered as branching into deeper levels, meaning that a block of `\begin{itemize}...\end{itemize}` is considered as a higher component with each point being a next-level element.

- **Exclusions:** References sections should **not** be parsed into the hierarchy.

- **Inclusions:** Acknowledgements and Appendices (often unnumbered using `\section*`) **must** be included.

### Standardization and Deduplication

##### Cleanup and Normalization

Students must clean and normalize the data within the hierarchy:

- **LaTeX Cleanup:** Remove unnecessary formatting commands (e.g., `\centering`, `[htpb]`, `\midrule`) that do not contribute to semantic meaning.

- **Math Normalization:** Convert all inline mathematics to a unified format (e.g., `$...$`) and all block mathematics to a unified format (e.g., `\begin{equation}...\end{equation}`).

##### Reference Extraction

For citations defined using `\bibitem` within the `.tex` files, students must convert them into standard BibTeX entries using programmatic tools (e.g., Regular Expressions).

##### Deduplication

Deduplication is required at two levels:

- **Reference Entries:** Duplicated reference entries inside each version or across different versions of a single publication should be properly handled. If different citation keys (names) refer to the same underlying reference content, a single citation key should be chosen, and the `\cite{}` commands of the remaining entries must be renamed to this chosen key. Additionally, the deduplication process should unionize the fields of the duplicate entries rather than selecting one entry while discarding all other information.

- **Full-text Content:** Full-text content deduplication must be applied to the hierarchical elements. If an element's text content matches exactly across different versions (full-text match), it should be represented by a single identifier in the final output, reducing redundancy. Note: full-text matching should be performed *after* cleanup to remove discrepancies in minor details (such as formatting or spacing) that might otherwise cause the code to identify identical texts as different.

## Requirement

Process every publication produced in Milestone 1. For each publication, parse every version's LaTeX source (following the compilation path), build the hierarchical structure, standardize and deduplicate the content, and extract the references into a unified BibTeX file. The milestone thus produces two files per publication:

- **hierarchy.json**: the parsed content and the hierarchical structure, in the format defined below. This single JSON file replaces the raw `tex` folder from the previous Milestone for downstream consumption.

- **refs.bib**: the unified BibTeX entries after deduplication and merging from the hierarchy construction step.

There is **no data submission** in this milestone: the processed corpus stays with the group as the working input of Milestone 3. The following format is a suggested convention—follow it as-is or adapt it to whatever is most convenient for your group; the final data submission on Hugging Face (defined in Milestone 3) can be produced either way.

**Format for hierarchy.json:**

```
{
  "elements": {
    "smallest-element-id": "Cleaned latex content ...",
    "higher-component-id": "Title of the associated content"
  },
  "hierarchy": {
    "1": { // Version 1
      "higher-component-id": "root-document-id", // parent
      "smallest-element-id": "higher-component-id" // parent
    },
    "2": { // Version 2
       "id-string-x": "id-string-y" // parent
    }
  }
}
```

**Note:**

1.  The `elements` field contains elements from **all** versions of the publication. These elements must be deduplicated; meaning if an element's text content matches exactly across versions (full-text match), it should be represented by a single id-string.

2.  The ID elements should contain information about the publication ID (arXiv ID or Semantic Scholar ID) to identify which publication the element belongs to, while the remaining part of the ID should discriminate between elements inside that publication.

## Submission Format

### Source Code

This milestone's code is committed to the same single public GitHub repository used in Milestone 1, continuing the cumulative history that documents the group's progress. The repository contains only source files such as Python files (`.py` or `.ipynb`)—excluding data files, compiled executables, or any other non-source materials—together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup and code execution
```

This milestone is submitted via Moodle as a group by pasting the public links to the shared code repository and to the milestone report (see below). All the submissions above should be in the official language of your program. **NO late submission is permitted**.

### Report Requirements (Jupyter Book)

Students must prepare a milestone report compiled as a **Jupyter Book**—the same book repository introduced in Milestone 1, hosted on its GitHub Pages—adding a parsing-and-standardization section to that book rather than creating a new one. The book must present the statistics and analysis of the processed data, and its figures and tables must be *generated during book compilation* (not pasted as static screenshots) for quality and interactivity. The report should specifically cover:

- **Hierarchical Parsing:** Explanation of the logic used to detect file structure, parse the LaTeX hierarchy, and handle multi-file inputs.

- **Standardization:** Details on how data cleaning, math normalization, and reference deduplication were implemented.

- **Statistics:** Relevant statistics such as the success rate of parsing and the element/entry counts before and after deduplication.

The parser's performance should also be illustrated through two main points: running time (such as the end-to-end wall time of the parser and the average time to process one publication) and memory footprint (such as the maximum RAM used and the final output's storage size). The testbed for the final benchmarking is a Google Colab instance running on CPU-only mode. No upper limit on the running time is enforced, while the upper limit on maximum disk usage is given by the Colab instance.

The `README.md` of the repository stays separate: it provides clear instructions on setting up the necessary environment (e.g., Python version, required packages via pip or conda) and running the code with specific configurations.

## Grading Criteria

Your grade is determined upon five main criteria as listed below:

- **Hierarchical Parser:** Accuracy of the parser in detecting structure, handling multi-file sources, and identifying the appropriate hierarchical levels.

- **Standardization & Deduplication:** Correct cleanup, math normalization, reference extraction, and both deduplication levels (reference entries with `\cite` renaming and field unionization; full-text content across versions).

- **Parser's Performance:** How efficient the parser is (running time, memory footprint).

- **Code Quality & Reproducibility:** Clean, runnable code with clear instructions.

- **Report (Jupyter Book):** Figures generated at book compilation, interactivity, and clarity of the hosted book.

---

<a id="milestone-matching"></a>

## Project Milestone 3 — Reference Matching Pipeline

[Trang nguồn](https://hcmus-cs-ta.github.io/lab-book/intro-ds/statement/matching/) · [Bản Markdown gốc](https://hcmus-cs-ta.github.io/lab-book/build/matching-2d60b420e66b754d7a0bd40bac975dec.md)

## Objectives

In this milestone, students will apply machine learning techniques to a real matching problem: the citation entries extracted from the parsed text are linked with their external metadata. Concretely, the BibTeX entries produced in Milestone 2 must be matched to the correct arXiv IDs in the `references.json` crawled in Milestone 1 via the Semantic Scholar API [^matching-semantic-scholar-api][^matching-semantic-scholar-platform]. This practice mimics the real-world data science workflow of entity resolution—unstructured text processing, standardization, feature engineering, and matching algorithms—assembled into a complete pipeline.

## Description

Students must perform a matching task between the references extracted and standardized in Milestone 2 and the scraped `references.json` data. The goal is to identify which extracted BibTeX entry corresponds to which arXiv ID (or metadata entry) in the `references.json` file. The full data science pipeline is described below.

### Data Cleaning

Perform any additional text preprocessing required to facilitate the matching process (e.g., lowercasing, stop-word removal, or specific tokenization for author names and titles).

### Data Labelling

Students need to create a ground truth dataset by labelling associations between the extracted BibTeX entries and the entries in `references.json`. The task is to link the converted BibTeX entries from the LaTeX source to the correct arXiv ID found in the `references.json` file. Students are required to:

- Manually label references for at least **5 publications**. The manual ground truth dataset must contain a total of at least **20 labeled reference pairs** (associations between a BibTeX entry and a target arXiv ID).

- Implement automatic matching based on classic tools (such as regex, string similarity heuristics, etc.) to generate labels for at least **10%** of the remaining non-manual data.

The internal format for these labels is up to the students but must be clearly documented in the group's repository and presented in the poster.

### Feature Engineering

Students must first frame the matching task as a specific supervised learning problem (e.g., classification, regression, recommendation, or ranking), which determines the input format (e.g., entry-reference pairs, triplets, or candidate lists). Based on this chosen input format, students must perform feature engineering to construct reasonable features for the model. These features can range from simple string matching scores or embeddings to complex statistical features.

Students must justify the creation of each feature in the poster and the repository documentation, explaining the underlying idea. This insight and idea should be illustrated with appropriate data analysis.

**Note:** In this feature engineering phase, students are allowed to construct features based on hierarchies previously formed in Milestone 2.

### Data Modeling

The target of this problem is to match the entries inside the standardized BibTeX file with associated references inside `references.json` of the same publication.

If there are $m$ BibTeX entries in the merged BibTeX file and $n$ references inside the scraped Semantic Scholar `references.json`, then there are $m \times n$ possible pairs inside that single publication. Thus, there are actually $m \times n$ data points generated from this publication only. Consequently, $m \times n$ labels should be assigned, where each pair has a binary label of yes or no, indicating whether the BibTeX entry from the `.bib` file corresponds to the associated reference in `references.json`.

The data split strategy is as follows:

- **Test Set:** Includes 1 publication from the manually labeled set and 1 publication from the automatically matched set.

- **Validation Set:** Includes 1 publication from the manually labeled set and 1 publication from the automatically matched set.

- **Training Set:** Consists of all remaining publications (the remaining manually labeled ones and the remaining automatically matched ones).

### Model Evaluation

Evaluate the trained models on the **Test set** (comprising the 2 publications defined above). The model should output a ranked list of the **top 5 candidates** from `references.json` for each BibTeX entry. Post-processing of the results is allowed.

The evaluation metric is **Mean Reciprocal Rank (MRR)**.

$$\text{MRR} = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \frac{1}{\text{rank}_i}$$

Where $|Q|$ is the total number of references to match, and $\text{rank}_i$ is the rank position of the correct match within the top 5 candidates. If the correct match is not in the list, the score is zero.

## Requirement

Perform the full pipeline (cleaning, labelling, feature engineering, modeling, evaluation) on the assigned publications. The matching results are published in the `predictions` table of the final Hugging Face dataset (see the Submission Format section). The table contains one row per BibTeX entry of each publication:

| **Column** | **Type** | **Content** |
|:---|:---|:---|
| arxiv_id | string, non-null | Publication the entry belongs to |
| partition | string, dictionary | `train`, `valid`, or `test` |
| citation_key | string, non-null | BibTeX entry name (identifier) |
| groundtruth_arxiv_id | string, nullable | The correct arXiv ID from `references.json`, when known |
| cand_1–cand_5 | string, nullable | The model's ranked top-5 candidates: cand_1 best, cand_5 last |
*Columns of the predictions table*

**Important Note:** Only the publications that are used for the reference matching task (those in the Training, Validation, and Test sets) have rows in this table.

## Submission Format

### Final Data Submission (Hugging Face)

There is **no intermediate data submission** in this project. The final data submission happens in this milestone: the fully processed data is hosted as a public **Hugging Face dataset**—following the hosting instructions given by the Lab Instructors—and the dataset link is pasted via Moodle.

**Storage format: Parquet.** Publish the processed corpus as *sharded Parquet*—the Hub's standard dataset format, which the viewer and the streaming backend read directly—in seven tables with one unified, explicit schema. Keep the columns flat and primitive: one-level string lists (authors, revised dates) are fine, nested objects and serialized JSON blobs are not.

| **Table** | **Columns (types)** | **Built from** |
|:---|:---|:---|
| papers | arxiv_id (string, non-null); title (string); authors (list of strings); submission_date (ISO string); revised_dates (list of strings); venue (string, nullable) | the crawled paper metadata |
| elements | element_id (string, non-null); arxiv_id (string, non-null); kind (string, dictionary); content (string) | the parsed hierarchy, deduplicated across versions |
| element_parents | arxiv_id (string); version (int); element_id (string, non-null); parent_id (string, non-null) | the per-version parent maps of the parsed hierarchy |
| bibtex_entries | arxiv_id (string); citation_key (string, non-null); entry_type (string, dictionary); title (string); authors (list of strings); year (int, nullable); doi (string); journal (string); url (string) | the unified BibTeX entries, fields normalized into these columns |
| paper_references | arxiv_id (string); ref_arxiv_id (string, non-null); ref_title (string); ref_authors (list of strings); ref_submission_date (string); ref_s2_id (string) | the crawled reference metadata, one row per citing–cited pair |
| predictions | The columns are specified in the Requirement section | the matching results |
| sources | arxiv_id (string); version (int); filename (string); content (string) | LaTeX/BibTeX source text per version |
*Tables of the final dataset and their columns*

The dataset repository itself is simple:

    └── <dataset-repo>/
        ├── README.md
        └── data/
            ├── papers/
            ├── elements/
            ├── element_parents/
            ├── bibtex_entries/
            ├── paper_references/
            ├── predictions/
            └── sources/

At the root, a **dataset card** (`README.md` with YAML metadata) tells the Hub how the tables map to files:

**Dataset card metadata (README.md):**

```
---
configs:
- config_name: papers
  data_files:
  - split: train
    path: data/papers/*.parquet
- config_name: elements
  data_files:
  - split: train
    path: data/elements/*.parquet
- ...one config per table...
---
```

The intermediate working formats of Milestones 2 and 3 are up to the group (the suggestions given there are conventional)—this table layout is only the publishing format for the final submission. Avoid custom loading scripts: the filename patterns and the card above are all the Hub needs. **NO late submission is permitted**.

### Source Code

This milestone's code is committed to the same single public GitHub repository used in Milestones 1 and 2, continuing the cumulative history that documents the group's progress. The repository contains only source files such as Python files (`.py` or `.ipynb`)—excluding data files, compiled executables, or any other non-source materials—together with:

```
<group-repo>/
|-- src # folder containing the source code
|   |-- *.{py/ipynb}
|   |-- requirements.txt # To re-produce the environment
|-- README.md # Instructions on environment setup, code execution, feature and label documentation
```

This milestone is submitted via Moodle as a group: the poster file (see below) and the public links to the Hugging Face dataset and to the shared code repository. All the submissions above should be in the official language of your program.

### Poster and Poster Session

The final grading format is a **poster session**. Each group submits **one pptx file containing a single-page poster** in the form factor of **portrait A2** for review. The poster should present the group's selected pieces of work: those representing the *highest quality*, the *most outstanding* results, and the work the group believes makes it *distinct from the others*—for example, the engineered features with their justification and analysis, the model and its MRR results, and notable statistics of the parsing and matching pipeline.

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
