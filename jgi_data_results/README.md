# JGI Data Results

This directory contains results from fetching and processing genomic sequencing reads from the [JGI Data Portal](https://data.jgi.doe.gov/) using the IMG (Integrated Microbial Genomes) database, and analyzed using the KBase Research Agent.

## Overview

The data processing workflow integrates JGI sequencing project metadata with IMG genome identifiers and the KBase Research Agent to validate and annotate genomic read samples. This gives a demonstration of how the Agent can be used to efficiently analyze many large datasets without human intervention, and produce a readable report.

## Process: `jgi_data_portal.ipynb`

The Jupyter notebook `jgi_data_portal.ipynb` implements the following workflow:

### 1. **Querying the JGI Data Portal API**
   - Uses the JGI Files API (`https://files.jgi.doe.gov/search/`) to search for sequencing project data
   - Queries can be performed using:
     - Scientific program names (e.g., "Microbial")
     - Specific JGI sequencing project IDs
     - Advanced search filters and parameters
   - The API returns structured JSON responses containing organism metadata and associated sequence files

### 2. **Extracting File and Metadata Information**
   - Parses API responses to extract key information:
     - **JGI sequencing project ID**: Unique identifier for the sequencing project
     - **IMG genome ID**: Integrated Microbial Genomes database identifier
     - **File ID**: KBase file system ID
     - **File name**: Original FASTQ sequence file name (often includes barcode/multiplexing info)
     - **Original UPA**: KBase Workspace User Project Address pointing to the raw read data
     - **Species name**: Original IMG-based taxonomic classification

### 3. **Narrative Generation**
   - Generated narrative IDs and URLs track KBase workspace narratives created during the analysis pipeline
   - Each sample is processed in a narrative environment for downstream analysis (assembly, annotation, etc.)
   - Narratives serve as reproducible computational records for each sample

### 4. **GTDB Taxonomic Annotation**
   - Integrates GTDB (Genome Taxonomy Database) predictions for modern, standardized taxonomy
   - Performs species-level or higher-rank taxonomic classification
   - Enables comparison with legacy IMG taxonomy to assess alignment between classification systems

### 5. **Match Status Classification**
   - Compares original IMG species annotation with GTDB-Tk predictions from the final result of KBase Research Agent runs (where appropriate for the data).
   - Categorizes matches into standardized categories (see Results section below)

## Results Files

### `img_llm_annotations_with_gtdb.tsv` (Primary Output)

Tab-separated file containing 100 annotated samples with the following columns:

| Column | Description |
|--------|-------------|
| **JGI sequencing project id** | Unique JGI project identifier for the sequencing run |
| **IMG genome id** | Integrated Microbial Genomes database identifier |
| **File id** | JGI file system identifier for the FASTQ read file |
| **File name** | Original FASTQ file name with sequencing barcodes/multiplex info |
| **Original upa** | KBase Unique Permanent Address - a unique data object identifier (format: narrative_id/object/version) |
| **Generated narrative id** | KBase narrative id created for this sample |
| **Narrative url** | Direct link to the KBase narrative for interactive analysis |
| **Species name** | Original IMG-based taxonomic classification |
| **GTDB Predicted Species** | GTDB-predicted taxonomic classification (species, genus, or phylum level) |
| **Match Status** | Classification of alignment between IMG and GTDB predictions |

### Match Status Categories

Results show six categories of taxonomic prediction accuracy:

| Category | Count | Interpretation |
|----------|-------|-----------------|
| **EXACT MATCH** | 15 | IMG and GTDB predictions match at species level |
| **MATCH - Phylum level** | 45 | Predictions align at phylum level (most common case) |
| **PARTIAL - Same genus** | 14 | Same genus but different species prediction |
| **UNCLASSIFIED** | 13 | GTDB assigned "Unclassified Bacteria" (insufficient confidence) |
| **MISMATCH - Different genus** | 6 | IMG and GTDB predictions differ at genus level |
| **MISSING GTDB DATA** | 7 | GTDB data unavailable for this IMG genome |

### `img_llm_annotations.tsv` (Supplementary File)

Contains the same 100 samples without GTDB annotations, showing only the original JGI/IMG metadata and generated narrative information. Useful for tracking the mapping between JGI project IDs and KBase narratives.

## Key Insights

1. **High Phylum-Level Consistency**: 45% of predictions match at the phylum level, indicating reasonable taxonomic consistency between IMG and GTDB at higher ranks.

2. **Species-Level Exact Matches**: Only 15% show exact species-level matches, reflecting both taxonomic annotation methodology differences and potential genuinely different organism identifications.

3. **Genus-Level Partial Matches**: 14% of samples remain at the same genus but with different species predictions, suggesting fine-grained taxonomic differences.

4. **Unclassified Cases**: 13% received "Unclassified Bacteria" from GTDB, often indicating novel organisms or sequences with limited reference data.

5. **Missing Data**: 7% of IMG genomes lack GTDB coverage, highlighting coverage gaps in the GTDB database.

6. **Mismatches**: 6% show true genus-level mismatches, potentially indicating annotation errors or novel taxonomy.

## Related Resources

- [JGI Data Portal](https://files.jgi.doe.gov/) - Source of sequencing data
- [IMG Database](https://img.jgi.doe.gov/) - Original genome annotations
- [GTDB Website](https://gtdb.ecogenomic.org/) - Genome taxonomy database
- [KBase Documentation](https://docs.kbase.us/) - KBase workspace and narrative information
