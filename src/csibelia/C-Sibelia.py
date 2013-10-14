#!/usr/bin/python

import re
import os
import sys
import time
import glob
import shutil
import tempfile
import argparse
import itertools
import functools
import subprocess
import collections
import multiprocessing

COVER = 1
UNCOVER = 0
LINE_LENGTH = 60
MINIMUM_CONTEXT_SIZE = 30
BLOCKS_FILE = 'blocks_sequences.fasta'
INSTALL_DIR = os.path.dirname(os.path.abspath(__file__))
LAGAN_DIR = os.path.join(INSTALL_DIR, '..', 'lib', 'Sibelia', 'lagan')
os.environ['LAGAN_DIR'] = LAGAN_DIR

FastaRecord = collections.namedtuple('FastaRecord', ['seq', 'description', 'id'])
SyntenyBlock = collections.namedtuple('SyntenyBlock', ['seq', 'chr_id', 'strand', 'id', 'start', 'end', 'chr_num'])
AlignmentRecord = collections.namedtuple('AlignmentRecord', ['body', 'block_instance'])

class FailedStartException(Exception):
	pass

class DuplicatedSequenceIdException(Exception):
	def __init__(self, id):
		self._id = id
		
	def __str__(self):
		return 'Found duplicated sequence id "%s"' % (self._id)

def unzip_list(zipped_list):
	return ([x for (x, _) in zipped_list], [y for (_, y) in zipped_list])

def parse_blocks_coords(blocks_file):		
	group = [[]]
	num_seq_id = dict()
	seq_id_num = dict()
	line = [l.strip() for l in open(blocks_file) if l.strip()]	
	for l in line:
		if l[0] == '-':
			group.append([])
		else:
			group[-1].append(l)			
	for l in group[0][1:]:	
		l = l.split()
		num_seq_id[l[0]] = l[2]
		seq_id_num[l[2]] = int(l[0])		
	ret = dict()
	for g in [g for g in group[1:] if g]:		
		block_id = int(g[0].split()[1][1:])
		ret[block_id] = []	
		for l in g[2:]:
			l = l.split()
			chr_id = num_seq_id[l[0]]
			start = int(l[2])
			end = int(l[3])
			chr_num = int(l[0])
			ret[block_id].append(SyntenyBlock(seq='', chr_id=chr_id, strand=l[1], id=block_id, start=start, end=end, chr_num=chr_num))		
	return (ret, seq_id_num)

def reverse_complementary(seq):
	comp = dict()
	comp['A'] = 'T'
	comp['T'] = 'A'
	comp['C'] = 'G'
	comp['G'] = 'C'
	return ''.join([(comp[ch] if ch in comp else ch) for ch in seq[::-1]])

def strip_chr_id(chr_id):
	part = chr_id.split('|')
	if len(part) == 5:
		return part[-2].split('.')[0]
	return chr_id

def parse_fasta_file(file_name):	
	handle = open(file_name)
	line = [line.strip() for line in handle if line.strip() != '']
	record = []
	i = 0
	while i < len(line):
		if line[i][0] == '>':
			j = i + 1
			while j < len(line) and line[j][0] != '>':
				j += 1
			seq = ''.join(line[i + 1:j])
			description = line[i][1:].strip()
			seq_id = description.split()[0]
			record.append(FastaRecord(seq=seq, description=description, id=seq_id))
			i = j
		else:
			i += 1		
	handle.close()
	return record

def write_wrapped_text(text, handle):
	pos = 0
	while pos < len(text):
		end = min(pos + LINE_LENGTH, len(text))
		print >> handle, text[pos:end]
		pos = end

def write_fasta_records(fasta_record, file_name):	
	handle = open(file_name, 'w')
	for record in fasta_record:
		print >> handle, '>' + record.description		
		write_wrapped_text(record.seq, handle)
	handle.close()

class Variant(object):
	def __init__(self, reference_chr_id, reference_pos, contig_id, assembly_pos, reference_allele,
				 assembly_allele, reference_context, assembly_context, synteny_block_id):
		self._reference_chr_id = '.' if reference_chr_id is None else reference_chr_id
		self._reference_pos = '.' if reference_pos is None else reference_pos  		
		self._contig_id = str(contig_id)
		self._assembly_pos = assembly_pos
		self._reference_allele = '.' if reference_allele is None else reference_allele.upper()  
		self._assembly_allele = '.' if assembly_allele is None else assembly_allele.upper()
		self._reference_context = '.' if reference_context is None else reference_context.upper()
		self._assembly_context = '.' if assembly_context is None else assembly_context.upper()
		self._synteny_block_id = '.' if synteny_block_id is None else synteny_block_id

	def __str__(self):
		return "\t".join([str(self._reference_pos), self._reference_allele, self._assembly_allele,
						str(self._synteny_block_id), self._contig_id,
						self._reference_context, self._assembly_context])
				
	def get_synteny_block_id(self):
		return self._synteny_block_id
	
	def get_assembly_pos(self):
		return self._assembly_pos
	
	def get_reference_context(self):
		return self._reference_context
	
	def get_assembly_context(self):
		return self._assembly_context
			
	def get_reference_pos(self):
		return self._reference_pos
	
	def get_reference_chr_id(self):
		return self._reference_chr_id
	
	def get_contig_id(self):
		return self._contig_id
	
	def get_reference_allele(self):
		return self._reference_allele
	
	def get_assembly_allele(self):
		return self._assembly_allele
	
	def get_vcf_record(self):
		data = [strip_chr_id(self.get_reference_chr_id()), str(self.get_reference_pos()),
			'.', self.get_reference_allele(), self.get_assembly_allele(), '.', '.', '.']
		return '\t'.join(data)

def no_gaps(sequence):
	return ''.join([ch for ch in sequence if ch != '-'])

def get_context(alignment, alignment_segment, segment_index):
	context = []	
	if segment_index > 0:
		segment = alignment_segment[segment_index - 1]
		start = segment[1] - min(segment[1] - segment[0], MINIMUM_CONTEXT_SIZE)
		context.append(str(alignment[0][start:segment[1]]))
	else:
		context.append('')

	if segment_index + 1 < len(alignment_segment):
		segment = alignment_segment[segment_index + 1]
		end = segment[0] + min(segment[1] - segment[0], MINIMUM_CONTEXT_SIZE)
		context.append(str(alignment[0][segment[0]:end]))
	else:
		context.append('')
		
	segment = alignment_segment[segment_index]
	reference_context = context[0] + no_gaps(alignment[0][segment[0]:segment[1]]) + context[1]
	assembly_context = context[0] + no_gaps(alignment[1][segment[0]:segment[1]]) + context[1]
	return reference_context, assembly_context

def parse_alignment(alingment_file_name, reference_chr_id, synteny_block_id,
				 contig_id, reference_start, reference_direction, assembly_direction):	
	last_match = None
	start_position = None
	alignment_segment = []
	alignment = [record.seq for record in parse_fasta_file(alingment_file_name)]		
	for now_position, symbol in enumerate(zip(alignment[0], alignment[1])):
		now_match = symbol[0] == symbol[1]
		if last_match is None:
			last_match = now_match
			start_position = 0
		elif last_match != now_match:
			if last_match == False or now_position - start_position >= MINIMUM_CONTEXT_SIZE or start_position == 0:
				alignment_segment.append([start_position, now_position, last_match])
				start_position = now_position
			elif alignment_segment:
				start_position = alignment_segment[-1][0]
				del alignment_segment[-1]
			last_match = now_match
			
	alignment_segment.append([start_position, len(alignment[0]), last_match])
	position = reference_start
	reference_position_map = []
	for symbol in alignment[0]:
		reference_position_map.append(position)
		position += reference_direction if symbol != '-' else 0
	
	variant = []	
	for segment_index, segment in enumerate(alignment_segment):
		start, end, match = segment
		if match == False:
			shift = 1
			variant_reference_start = reference_position_map[start]
			reference_context, assembly_context = get_context(alignment, alignment_segment, segment_index)
			SNP = end - start == 1 and alignment[0][start] != '-' and alignment[1][start] != '-'
			if start == 0 or SNP:
				shift = 0
			reference_allele = no_gaps(alignment[0][start - shift:end])
			assembly_allele = no_gaps(alignment[1][start - shift:end])
			if reference_direction == -1:
				reference_allele = reverse_complementary(reference_allele)
				assembly_allele = reverse_complementary(assembly_allele)
				
			variant.append(Variant(reference_chr_id, variant_reference_start - shift, contig_id, None,
								reference_allele, assembly_allele, reference_context, assembly_context,
								synteny_block_id))				
	return variant

def get_seq(file_name):
	all_seq = [record for record in parse_fasta_file(file_name)]
	return [(record.id, record.seq) for record in all_seq ]	
	
def parse_header(header):
	ret = dict()
	header = header.split(',')
	for item in header:
		item = item.split('=')
		key = item[0]
		value = ''.join([ch for ch in item[1] if ch != "'" and ch != '"'])
		ret[key] = value
	return ret

def find_instance(instance_list, reference_seq_id, in_reference):
	for instance in instance_list:		
		if (instance.chr_id in reference_seq_id) == in_reference:
			return instance
	return None

def process_block(block, align, block_index):	
	pid = str(os.getpid()) + '_'	
	alignment_file = pid + 'align.fasta'
	unique, synteny_block_id, instance_list = block[block_index]
	if not align and not unique:
		return ([], [])
	file_name = [pid + str(i) + 'block.fasta' for i, _ in enumerate(instance_list)]	
	mlagan_cmd = [os.path.join(LAGAN_DIR, "mlagan")] + file_name
	lagan_cmd = ['perl', os.path.join(LAGAN_DIR, "lagan.pl")] + file_name + ['-mfa']
	alignment_handle = open(alignment_file, 'w')
	for index, block in enumerate(instance_list):
		description = block.chr_id + str(block.start)
		write_fasta_records([FastaRecord(id=block.chr_id, description=description, seq=block.seq)], file_name[index])
	
	cmd = lagan_cmd if unique else mlagan_cmd
	worker = subprocess.Popen(cmd, stdout=alignment_handle, stderr=subprocess.PIPE)
	_, stderr = worker.communicate()
	if worker.returncode != 0:
		raise FailedStartException(stderr)
	alignment_handle.close()
	alignment = [record.seq for record in parse_fasta_file(alignment_file)]
	alignment = [AlignmentRecord(body=align, block_instance=inst) for (align, inst) in zip(alignment, instance_list)]
	ret = []
	if unique:			
		reference_instance, assembly_instance = instance_list
		reference_start = reference_instance.start
		reference_chr_id = reference_instance.chr_id	
		contig_id = assembly_instance.chr_id				
		reference_direction = +1 if reference_instance.strand == '+' else -1
		assembly_direction = +1 if reference_instance.strand == '+' else -1
		ret = parse_alignment(alignment_file, reference_chr_id, synteny_block_id,
							contig_id, reference_start, reference_direction, assembly_direction)	
	for file_name in [alignment_file] + file_name:
		os.remove(file_name)
	return (ret, alignment)		

def get_size(record):
	return abs(record.end - record.start) + 1

def determine_unique_block(instance_list, reference_seq, min_block_size):
	if len(instance_list) == 2:
		reference_instance = find_instance(instance_list, reference_seq.keys(), True)
		assembly_instance = find_instance(instance_list, reference_seq.keys(), False)			
		if (not reference_instance is None) and (not assembly_instance is None):
			reference_size = get_size(reference_instance)
			assembly_size = get_size(assembly_instance)
			if reference_size >= min_block_size and assembly_size >= min_block_size:
				return (reference_instance, assembly_instance)
	return (None, None)

def depict_coverage(block_seq, reference_seq, assembly_seq, base_cover):
	if base_cover is None:
		base_cover = dict()
		for seq_group in (reference_seq, assembly_seq):		
			for seq_id, seq in seq_group.items():
				base_cover[seq_id] = [UNCOVER for _ in seq]			
	for block_id, instance_list in block_seq.items():
		reference = [instance for instance in instance_list if instance.chr_id in reference_seq]
		if reference and len(reference) < len(instance_list):
			for instance in instance_list:				
				start = min(instance.start, instance.end) - 1
				end = max(instance.start, instance.end)
				base_cover[instance.chr_id][start:end] = [block_id] * (end - start)
	return base_cover	
					
def call_variants(directory, min_block_size, proc_num):
	os.chdir(directory)
	coords_file_re = re.compile('blocks_coords[0-9]*.txt')	
	coords_file_list = [coords_file for coords_file in os.listdir('.') if coords_file_re.match(coords_file)]
	blocks_coords, seq_id_num = unzip_list([parse_blocks_coords(coords_file) for coords_file in coords_file_list])
	seq_id_num = seq_id_num[0]
	block_seq = dict()	
	for record in parse_fasta_file(BLOCKS_FILE):
		header = parse_header(record.description)
		chr_id = header['Seq']
		strand = header['Strand']
		block_id = int(header['Block_id'])
		start = int(header['Start'])
		end = int(header['End'])
		if block_id not in block_seq:
			block_seq[block_id] = []
		block = SyntenyBlock(chr_id=chr_id, seq=record.seq, id=block_id, strand=strand, start=start, end=end, chr_num=seq_id_num[chr_id])
		block_seq[block_id].append(block)

	pool = multiprocessing.Pool(proc_num)
	annotated_block = []	
	for synteny_block_id, instance_list in block_seq.items():
		unique = False		
		annotated_block.append((unique, synteny_block_id, instance_list))
															
	if annotated_block:		
		process_block_f = functools.partial(process_block, annotated_block, align)
		result = pool.map_async(process_block_f, range(len(annotated_block))).get()
		variant, alignment = unzip_list(result)
		pool.close()
		pool.join()
	else:
		variant = []
		alignment = []	
	
	for f in glob.glob('*block*block.anchors'):
		os.unlink(f)
	
	return alignment

def generate_conventional_output(variant_list, handle):
	for variant in variant_list:
		print >> handle, variant

def write_vcf_header(reference, handle):
	vcf_header = ['##fileformat=VCFv4.1', '##source=C-Sibelia 3.0.4', '##reference=' + strip_chr_id(reference.id)]
	table_header = ['#CHROM', 'POS', 'ID', 'REF', 'ALT', 'QUAL', 'FILTER', 'INFO']
	print >> handle, '\n'.join(vcf_header)
	print >> handle, '##INFO=<ID=SVTYPE,Number=1,Type=String,Description="Type of structural variant">'
	print >> handle, '##INFO=<ID=IMPRECISE,Number=0,Type=Flag,Description="Imprecise structural variation">'
	print >> handle, '##INFO=<ID=CIPOS,Number=2,Type=Integer,Description="Confidence interval around POS for imprecise variants">'
	print >> handle, '\t'.join(table_header)

def write_variants_vcf(variant_list, handle):	
	for variant in variant_list:
		print >> handle, variant.get_vcf_record()
		
def write_insertions_vcf(variant_list, reference_organism, handle):
	ref_len = str(len(reference_organism.seq))	
	reference_chr = strip_chr_id(reference_organism.id)
	for index, variant in enumerate(variant_list):
		ref_pos = '1'
		ref_allele = reference_organism.seq[0]
		contig = variant.get_contig_id()
		assembly_start = variant.get_assembly_pos() + 1
		assembly_end = assembly_start + len(variant.get_assembly_allele())
		start_alt_allele = ref_allele + '[' + contig + ':' + str(assembly_start) + '['
		end_alt_allele = ']' + contig + ':' + str(assembly_end) + ']' + ref_allele 
		start_bnd = 'bnd_' + str(index * 2)
		end_bnd = 'bnd_' + str(index * 2 + 1)
		info = ';'.join(('IMPRECISE', 'SVTYPE=BND', 'CIPOS=0,' + ref_len))
		start_record = [reference_chr, ref_pos, start_bnd, ref_allele, start_alt_allele, '.', '.', info]
		end_record = [reference_chr, ref_pos, end_bnd, ref_allele, end_alt_allele, '.', '.', info]
		for record in (start_record, end_record):
			print >> handle, '\t'.join(record)
			
def write_alignments_xmfa(alignment_list, handle):
	for group in alignment_list:
		for alignment in group:
			block = alignment.block_instance			
			print >> handle, ">%i:%i-%i %s %s" % (block.chr_num, block.start, block.end, block.strand, block.chr_id)
			write_wrapped_text(alignment.body, handle)
		print >> handle, '='

def write_insertions_text(variant_list, handle):
	header = ['SEQ_ID', 'POS', 'FRAGMENT']
	print >> handle, '\t'.join(header)
	for variant in variant_list:
		record = [variant.get_contig_id(), str(variant.get_assembly_pos() + 1), variant.get_assembly_allele()]
		print >> handle, '\t'.join(record)
		
def write_insertions_fasta(variant_list, file_name):
	record = []	
	for variant in variant_list:
		start = str(variant.get_assembly_pos() + 1)
		end = str(variant.get_assembly_pos() + len(variant.get_assembly_allele()))
		description = 'Seq="' + variant.get_contig_id() + '",Start=' + start + '",End=' + end
		record.append(FastaRecord(seq=variant.get_assembly_allele(), id=description, description=description))
	write_fasta_records(record, file_name)
	
def variant_key(variant):
	return (variant.get_reference_chr_id(), variant.get_reference_pos())

def handle_exception(e, temp_dir):
	print 'An error occured:', e
	shutil.rmtree(temp_dir, ignore_errors=True)

start = time.time()
parser = argparse.ArgumentParser(description='A tool for comparing two microbial genomes.', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument('genome', nargs='*', help='FASTA files')
parser.add_argument('-s', '--parameters', help='Parameters set, used for the simplification. \
					Option \"loose\" produces fewer blocks, but they are larger (\"fine\" is opposite).', 
					default='fine')
parser.add_argument('-m', '--minblocksize', help='Minimum size of a synteny block', type=int, default=500)
parser.add_argument('-p', '--processcount', help='Number of running processes', type=int, default=1)
parser.add_argument('-i', '--maxiterations', help='Maximum number of iterations during a stage of simplification',
					type=int, default=4)
parser.add_argument('-a', '--alignment', help='Output file for storing alignments in XMFA format', default="alignment.xmfa")
parser.add_argument('--debug', help='Generate output in text files', action='store_true')
group = parser.add_mutually_exclusive_group()
group.add_argument('-t', '--tempdir', help='Directory for temporary files')
group.add_argument('-o', '--outdir', help='Directory for synteny block output files')
args = parser.parse_args()

print args.genome
exit(0)

try:
	if args.outdir is None:
		if args.tempdir is None:
			try:
				temp_dir = tempfile.mkdtemp(dir='.')
			except EnvironmentError as e:
				print e
				exit(1)
		else:
			temp_dir = args.tempdir
	else:
		temp_dir = args.outdir	

	sibelia_cmd = [os.path.join(INSTALL_DIR, 'Sibelia'), 					
				' '.join(args.genome),
				'-q', 
				'--correctboundaries',
				'--nopostprocess',
				'--allstages',
				'--lastk', '30',
				'-m', str(args.minblocksize), 
				'-o', temp_dir,
				'-s', args.parameters,
				'-i', str(args.maxiterations),
				'-r']
	print >> sys.stderr, "Calculating synteny blocks..."

	worker = subprocess.Popen(sibelia_cmd, stdout=None, stderr=subprocess.PIPE)
	_, stderr = worker.communicate()
	if worker.returncode != 0:
		raise FailedStartException(stderr)

	print >> sys.stderr, "Performing alignment..."
	alignment_list = call_variants(temp_dir, args.minblocksize, args.processcount)
	alignment_file = args.alignment if args.outdir is None else os.path.join(args.outdir, args.alignment)
	alignment_handle = open(alignment_file, 'w')
	write_alignments_xmfa(alignment_list, alignment_handle)
	alignment_handle.close()
			
	if args.outdir is None:
		shutil.rmtree(temp_dir)	
	
except FailedStartException as e:
	handle_exception(e, temp_dir)
except EnvironmentError as e:
	handle_exception(e, temp_dir)
except DuplicatedSequenceIdException as e:
	handle_exception(e, temp_dir)

	

