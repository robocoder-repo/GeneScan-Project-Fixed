"""Convert Ensembl BMTSV files to minimal TSVs for Ideogram.js domain caches

Ideogram uses cached gene data to drastically simplify and speed up rendering.

Example call (including supplementary commands):
time python3 cache/domain_cache.py --output-dir ../../dist/data/cache/gene-domains-all-compressed/ --reuse-bmtsv; gzip -dkf ../../dist/data/cache/gene-domains-all-compressed/homo-sapiens-gene-domains.tsv.gz; tput bel
"""

import argparse
import codecs
import csv
import gzip
import os
import re
import sys
import urllib.request
from urllib.parse import quote
import json

# Enable importing local modules when directly calling as script
if __name__ == "__main__":
    cur_dir = os.path.join(os.path.dirname(__file__))
    sys.path.append(cur_dir + "/..")

from lib import download
from gene_cache import trim_id, detect_prefix, fetch_gff, parse_gff_info_field, fetch_interesting_genes
from gene_structure_cache import fetch_canonical_transcript_ids
from compress_transcripts import noncanonical_names

# Organisms configured for gene caching, and their genome assembly names
assemblies_by_org = {
    "Homo sapiens": "GRCh38",
    "Mus musculus": "GRCm38",
    "Danio rerio": "GRCz11",
    "Gallus gallus": "GRCg6a",
    "Rattus norvegicus": "Rnor_6.0",
    "Pan troglodytes": "Pan_tro_3.0",
    "Macaca fascicularis": "Macaca_fascicularis_5.0",
    "Macaca mulatta": "Mmul_10",
    "Canis lupus familiaris": "CanFam3.1",
    "Felis catus": "Felis_catus_9.0",
    "Equus caballus": "EquCab3.0",
    "Bos taurus": "ARS-UCD1.2",
    "Sus scrofa": "Sscrofa11.1",
    # "Anopheles gambiae": "AgamP4.51",
    "Caenorhabditis elegans": "WBcel235",
    "Drosophila melanogaster": "BDGP6.28"
}

ranked_genes_by_organism = {
    "Homo sapiens": "gene-hints.tsv",
    "Mus musculus": "pubmed-citations.tsv",
    "Rattus norvegicus": "pubmed-citations.tsv",
    "Canis lupus familiaris": "pubmed-citations.tsv",
    "Felis catus": "pubmed-citations.tsv",
}

biotypes = {}

# metazoa = {
#     "Anopheles gambiae".AgamP4.51.bmtsv.gz  "
# }

def sort_domains(domains, organism, canonical_ids):
    ranks = fetch_interesting_genes(organism)
    print('ranks[0:10]')
    print(ranks[0:10])
    print('domains[0:10]')
    print(domains[0:10])
    sorted_domains = []
    print('canonical_ids[0:3]')
    print(list(canonical_ids)[0:3])

    domains_with_genes = []
    for domain in domains:
        # E.g. FOO-BAR-404 -> FOO-BAR
        gene = "".join(domain[1].split('-')[:-1])
        domains_with_genes.append([gene] + domain)


    doms = domains_with_genes
    doms = sorted(
        doms,
        key=lambda d: d[1] in canonical_ids, reverse=True
    )
    domains_with_genes = doms


    # Sort genes by interest rank, and put unranked genes last
    trimmed_domains = sorted(
        domains_with_genes,
        key=lambda d: ranks.index(d[0]) if d[0] in ranks else 1E10,
    )

    # structs =
    # for id in structures_by_id:
    #     structs = structures_by_id[id]
    #     structs = sorted(structs, key=lambda s: s[0] in canonical_ids)
    #     structs = sorted(structs, key=lambda s: s[0] in canonical_ids)

    sorted_domains = []
    for domain in trimmed_domains:
        sorted_domains.append(domain[2:])

    print('sorted_domains[0:10]')
    print(sorted_domains[0:10])

    return sorted_domains

def get_domains_url(organism):
    """Get URL to domains TSV file, from Ensembl BioMart
    E.g. https://www.ensembl.org/biomart/martservice?query=%3C%21DOCTYPE%20Query%3E%0A%3CQuery%20%20virtualSchemaName%20%3D%20%22default%22%20formatter%20%3D%20%22TSV%22%20header%20%3D%20%220%22%20uniqueRows%20%3D%20%220%22%20count%20%3D%20%22%22%20datasetConfigVersion%20%3D%20%220.6%22%20%3E%0A%09%09%09%0A%09%3CDataset%20name%20%3D%20%22hsapiens_gene_ensembl%22%20interface%20%3D%20%22default%22%20%3E%0A%09%09%3CFilter%20name%20%3D%20%22with_interpro%22%20excluded%20%3D%20%220%22%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22ensembl_transcript_id%22%20%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22interpro%22%20%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22interpro_short_description%22%20%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22interpro_description%22%20%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22interpro_start%22%20%2F%3E%0A%09%09%3CAttribute%20name%20%3D%20%22interpro_end%22%20%2F%3E%0A%09%3C%2FDataset%3E%0A%3C%2FQuery%3E

    """

    # E.g. "Homo sapiens" -> "hsapiens"
    split_org = organism.split()
    brief_org = (split_org[0][0] + split_org[1]).lower()

    query = quote((
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<!DOCTYPE Query>'
        '<Query virtualSchemaName = "default" formatter = "TSV" header = "0" uniqueRows = "0" count = "" datasetConfigVersion = "0.6" >' +
          '<Dataset name = "' + brief_org + '_gene_ensembl" interface = "default" >' +
            '<Filter name = "with_interpro" excluded = "0"/>' +
            '<Attribute name = "ensembl_transcript_id" />' +
            '<Attribute name = "interpro" />' +
            '<Attribute name = "interpro_short_description" />' +
            '<Attribute name = "interpro_description" />' +
            '<Attribute name = "interpro_start" />' +
            '<Attribute name = "interpro_end" />' +
        '</Dataset>' +
        '</Query>'
    ).encode("utf-8"))
    url = f"https://www.ensembl.org/biomart/martservice?query={query}"
    return url

def parse_domain(row):
    """Return parsed transcript-related domain from CSV-reader-split row of GFF file"""
    feat_type = row[2]


    return domain

def parse_bmtsv(bmtsv_path):
    """Parse BMTSV into a set of Ensembl canonical transcript IDs
    """
    print(f"Parsing BMTSV: {bmtsv_path}")
    transcript_ids = []

    with open(bmtsv_path) as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            id = row[0]
            transcript_ids.append(id)

    return set(transcript_ids)

def get_length(start, stop):
    length = str(int(stop) - int(start))
    return length

def compress_biotype(biotype, biotype_map):
    if biotype:
        return biotype_map[biotype]
    else:
        last = sort(list(biotype_map.values()))[-1]
        new_last = last + 1

subpart_map = {
    'five_prime_UTR': '0',
    'exon': '1',
    'three_prime_UTR': '2',
}

def parse_domains(domains_path, gff_path, gff_url):
    """Parse proteins domains from InterPro data in TSV file
    """

    transcript_names_by_id = {}
    with open(gff_path) as file:
        reader = csv.reader(file, delimiter="\t")
        for gff_row in reader:
            if gff_row[0][0] == "#":
                # Skip header
                continue

            feat_type = gff_row[2]
            if feat_type != "mRNA": continue
            info = gff_row[8]
            info = parse_gff_info_field(info)
            transcript_id = info["ID"].split('transcript:')[1]
            transcript_name = info["Name"]
            transcript_names_by_id[transcript_id] = transcript_name


    missing_transcripts = []
    domain_names_by_id = {}
    domains_by_transcript = {}
    prev_domain = None
    i = 0
    with open(domains_path) as file:
        reader = csv.reader(file, delimiter="\t")
        for row in reader:
            i += 1

            if row[0][0] == "#":
                # Skip header
                continue

            # domain = parse_domain(row)
            domain = row

            if domain == None:
                continue

            # print('domain', domain)

            if (i % 50000 == 0):
                print(f"On entry {i}")
                print(domain)

            # if i > 100000:
            #     # return domains_by_transcript
            #     break

            transcript_id = domain[0]
            if transcript_id not in transcript_names_by_id:
                missing_transcripts.append(transcript_id)
                continue
            transcript_name = transcript_names_by_id[transcript_id]
            domain_id = trim_id(domain[1], "IPR")
            domain_name = domain[3]
            [start, stop] = domain[4:6]
            length = str(int(stop) - int(start))
            if domain_id not in domain_names_by_id:
                domain_names_by_id[domain_id] = domain_name

            parsed_domain = ';'.join([domain_id, start, length])

            if transcript_name in domains_by_transcript:
                domains_by_transcript[transcript_name].append(parsed_domain)
            else:
                domains_by_transcript[transcript_name] = [parsed_domain]

            # [chr, start, stop, transcript, symbol, desc] = parsed_gene
            # length = str(int(stop) - int(start))

            # if prefix == None:
            #     prefix = detect_prefix(transcript)
            # slim_transcript = trim_transcript(transcript, prefix)

            # slim_genes.append([chr, start, length, slim_transcript, symbol, desc])

    num_missing = str(len(missing_transcripts))
    print('Number of transcript IDs lacking names:' + num_missing)

    tx_ids_by_name = {v: k for k, v in transcript_names_by_id.items()}

    domains = []
    for transcript in domains_by_transcript:
        tx_domains = domains_by_transcript[transcript]
        transcript_id = tx_ids_by_name[transcript]
        tx_domains.insert(0, transcript)
        tx_domains.insert(0, transcript_id)
        domains.append(tx_domains)

    print('domains[0:10]')
    print(domains[0:10])
    return [domains, domain_names_by_id]


class DomainCache():
    """Convert Ensembl BioMart TSVs to compact TSVs for Ideogram.js caches
    """

    def __init__(self, output_dir="data/", reuse_bmtsv=False):
        self.output_dir = output_dir
        self.tmp_dir = "data/"
        self.reuse_bmtsv = reuse_bmtsv

        self.biotype_map = []

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        if not os.path.exists(self.tmp_dir):
            os.makedirs(self.tmp_dir)

    def fetch_domains_tsv(self, organism):
        """Download an organism's domains TSV file from Ensembl BioMart
        """
        print(f"Fetching via Ensembl BioMart TSV for {organism}")
        url = get_domains_url(organism)
        domains_dir = self.tmp_dir + "domains/"
        if not os.path.exists(domains_dir):
            os.makedirs(domains_dir)
        org_lch = organism.lower().replace(" ", "-")
        domains_path = domains_dir + org_lch + "-domains.tsv"
        try:
            download(url, domains_path, cache=self.reuse_bmtsv)
        except urllib.error.HTTPError:
            # E.g. for C. elegans
            url = url.replace("chr.", "")
            download(url, domains_path, cache=self.reuse_bmtsv)
        return [domains_path, url]

    def write(self, domains, organism, names_by_id):
        """Save fetched and transformed gene data to cache file
        """
        # biotypes_list = list(biotypes.keys())
        # biotype_keys = ", ".join([
        #     f"{str(i)} = {key}" for i, key in enumerate(biotypes_list)
        # ])

        headers = "\n".join([
            f"## Ideogram.js domain cache for {organism}"
        ]) + "\n"

        domain_keys = []
        for id in names_by_id:
            domain_keys.append(f"{id} = {names_by_id[id]}")
        headers += "## domain keys: " + "; ".join(domain_keys) + "\n"
        # print('domains')
        # print(domains)
        domain_lines = "\n".join(["\t".join(s) for s in domains])
        content = headers + domain_lines

        org_lch = organism.lower().replace(" ", "-")
        output_path = f"{self.output_dir}{org_lch}-domains.tsv.gz"
        with gzip.open(output_path, "wt") as f:
            f.write(content)
        print(f"Wrote gene domain cache: {output_path}")

    def populate_by_org(self, organism):
        """Fill gene caches for a configured organism
        """
        [canonical_ids, bmtsv_url] = fetch_canonical_transcript_ids(organism)
        [gff_path, gff_url] = fetch_gff(organism, self.output_dir, True)
        [domains_path, domains_url] = self.fetch_domains_tsv(organism)

        [domains, names_by_id] = parse_domains(domains_path, gff_path, gff_url)
        sorted_domains = sort_domains(domains, organism, canonical_ids)
        sorted_domains = noncanonical_names(sorted_domains)

        # print('domains')
        # print(domains)

        self.write(sorted_domains, organism, names_by_id)

    def populate(self):
        """Fill gene caches for all configured organisms

        Consider parallelizing this.
        """
        # for organism in assemblies_by_org:
        for organism in ["Homo sapiens"]:
            self.populate_by_org(organism)

# Command-line handler
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Directory to put outcome data.  (default: %(default))"
        ),
        default="data/"
    )
    parser.add_argument(
        "--reuse-bmtsv",
        help=(
            "Whether to use previously-downloaded raw BMTSVs"
        ),
        action="store_true"
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    reuse_bmtsv = args.reuse_bmtsv

    DomainCache(output_dir, reuse_bmtsv).populate()
