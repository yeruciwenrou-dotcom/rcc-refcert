# Notice

The source code in this repository is released under the MIT License. Citation
metadata for the software and associated RCC paper are provided in
[`CITATION.cff`](CITATION.cff).

## IBM Vigo measurement counts

Timothy Proctor, Kenneth Rudinger, Erik Nielsen, Kevin Young and Robin
Blume-Kohout published the counts in *Measuring the Capabilities of Quantum
Computers* (2021). The data are licensed under [Creative Commons Attribution
4.0 International](https://creativecommons.org/licenses/by/4.0/).
[Original dataset](https://doi.org/10.5281/zenodo.5197499) ·
[Associated paper](https://doi.org/10.1038/s41567-021-01409-7) ·
[License text](LICENSES/CC-BY-4.0.txt)

The [packaged histogram](src/rcc_refcert/workflows/data/ibm_vigo_counts.json)
transcribes the 12 nonzero outcome-count pairs on line 4 (including the
header) of `supplement/data/ibmq_vigo/11_06_19/data/dataset.txt`. It
preserves the bit strings and counts printed in that pyGSTi record. RCC
RefCert supplies a [qubit layout](src/rcc_refcert/workflows/data/ibm_vigo_layout.json)
and [source metadata](src/rcc_refcert/workflows/data/ibm_vigo_source.json) for
the JSON conversion.
