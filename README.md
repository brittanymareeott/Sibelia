Sibelia 3.0.0

Release date: 24.06.2013

Authors
=======

* Ilya Minkin (St. Petersburg Academic University)
* Nikolay Vyahhi (St. Petersburg Academic University)
* Mikhail Kolmogorov (St. Petersburg Academic University)
* Son Pham (University of California, San Diego)

Introduction
============
This package contains two programs:

* Sibelia -- "Sibelia" is a tool for finding synteny blocks in closely related
genomes, like different strains of the same bacterial species. It takes a set
of FASTA files with genomes and locates coordinates of the synteny blocks in
these sequences. It also represents genomes as permutations of the blocks.

* C-Sibelia -- This tool is designed for comparison between two genomes
represented either in finished form or as sets of contigs. It is able to detect
SNPs/SNVs and indels of different scales. "C-Sibelia" works by locating synteny
blocks between the input genomes and aligning different copies of a block.
It considers only unique blocks, i.e. blocks having one copy in reference and
one copy in another genome.

Installation
============
See INSTALL.md file.

Usage
=====
See SIBELIA.md for "Sibelia" and C-SIBELIA.md for "C-Sibelia".

OS Support
==========
This version of "Sibelia" supports only "Linux"-based operating systems.
"Windows" users may try our web server http://etool.me/software/sibelia
or use a virtual machine. "Windows" support will be retained soon in the
future releases.

Citation
========
If you use "Sibelia" in your research, please cite:

Ilya Minkin, Anand Patel, Mikhail Kolmogorov, Nikolay Vyahhi, Son Pham.
"Sibelia: A fast synteny blocks generation tool for many closely related
microbial genomes" (accepted at WABI 2013).

License
=======
"Sibelia" is distributed under GNU GPL v2 license, see LICENSE.

It also uses third-party librarires:
* kseq.h (MIT License), author Heng Li
http://lh3lh3.users.sourceforge.net/kseq.shtml
* libdivsufsort (MIT License), author Yuta Mori
https://code.google.com/p/libdivsufsort
* TCLAP (MIT License), authors Michael E. Smoot and Daniel Aarno 
http://tclap.sourceforge.net
* Boost (Boost Software License)
http://www.boost.org
* D3.js (BSD License)
http://d3js.org
* Seqan (BSD/3-clause)
http://www.seqan.de

Contacts
========
E-mail your feedback at ivminkin@gmail.com.

You also can report bugs or suggest features using issue tracker at GitHub
https://github.com/bioinf/Sibelia/issues
