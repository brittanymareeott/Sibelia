#!/usr/bin/perl


while ($line = <STDIN>) {
    $line =~ /(.*)\s+([0-9]+)\s+([0-9]+);\s*(.*)\s+([0-9]+)\s+([0-9]+);\s*score\s* =\s*([0-9]*)\.?([0-9]*)\s*\(([+-])\)/;
    if ($9 eq "+" || $6 > $5) {
	print "$4 $5 $6; $1 $2 $3; score = $7.$8 ($9)\n";
    }
    else {
	print "$4 $6 $5; $1 $3 $2; score = $7.$8 ($9)\n";
    }

}
