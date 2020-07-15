#!/usr/bin/perl

# For KiwiSDR

# Gather decodes from FT8 log file /dev/shm/decode-ft8.log file of format 
#    163144   4 -0.9 2431 14074  KK5ZV VE5TLW R-16
# and create PSKReporter UDP datagram for upload per developer info
#  https://www.pskreporter.info/pskdev.html

# Process all messages to include
# CQ CALL1 GRID, CALL1 CALL2 GRID, CALL1 CALL2 RPT, CALL1 CALL2 RR73, etc.  
# cache call signs up to 5 minutes before resending (see $MINTIME)

# v0.2.7 - 2018/11/16 - K1RA@K1RA.us

# Start by using following command line
# ./pskr.pl YOURCALL YOURGRID
# ./pskr.pl WX1YZ AB12DE

use strict;
use warnings;

use IO::Socket;

# minimum number of minutes to wait before sending datagrams
my $MINTIME = 20;

# maximum UDP IPFIX datagram size in bytes minus header descriptor length
my $MAXDATA = 1250;

# PSKReporter upload address and port
my $peerhost = "report.pskreporter.info";
my $peerport = 4739;

# Software Descriptor for PSKReporter
my $decsw = "FT8-Skimmer v0.3";

# check for YOUR CALL SIGN
if( ! defined( $ARGV[0]) || ( ! ( $ARGV[0] =~ /\w\d+\w/)) ) { 
  die "Enter a valid call sign\n"; 
}
my $mycall = uc( $ARGV[0]);

# check for YOUR GRID SQUARE (6 digit)
if( ! defined( $ARGV[1]) || ( ! ( $ARGV[1] =~ /\w\w\d\d\w\w/)) ) { 
  die "Enter a valid 6 digit grid\n";
} 
my $mygrid = uc( $ARGV[1]);

if( ! defined( $ARGV[2]) ) { 
  die "Enter a valid file path of decode-ft8.log\n";
} 
my $logfile = $ARGV[2];

# IPFIX header
# 00 0A ll ll tt tt tt tt ss ss ss ss ii ii ii ii
# 'll ll' packet length, 'tt tt tt tt' UNIX time secs, 'ss ss ss ss' sequence number,
# 'ii ii ii ii' random id
my $header = "00 0a ";

# pack header into byte stream
$header = join( "", split(" ", $header));

# generate a unique ID - ii ii ii ii
my $rid = pack( "n", int( rand( 65535))) . pack( "n", int( rand( 65535)));

# Record Format Descriptors

# Receiver Info - receiverCallsign, receiverLocator, decodingSoftware 
my $rcvr = 
"00 03 00 24 99 92 00 03 00 00 " .
"80 02 FF FF 00 00 76 8F " .
"80 04 FF FF 00 00 76 8F " .
"80 08 FF FF 00 00 76 8F " .
"00 00";

# pack above into byte stream
$rcvr = pack( "H*", join( "", split(" ", $rcvr)));

# Sender Info - senderCallsign, frequency, sNR (1 byte), mode (1 byte), informationSource, senderLocator, flowStartSeconds
my $sndr = 
"00 02 00 3C 99 93 00 07 " .
"80 01 FF FF 00 00 76 8F " .
"80 05 00 04 00 00 76 8F " .
"80 06 00 01 00 00 76 8F " .
"80 0A FF FF 00 00 76 8F " .
"80 0B 00 01 00 00 76 8F " .
"80 03 FF FF 00 00 76 8F " .
"00 96 00 04";

# pack above into byte stream
$sndr = pack( "H*", join( "", split(" ", $sndr)));

# Receiver data header
my $rxhdr = "99 92 ";

# pack rxhdr into byte stream
$rxhdr = join( "", split(" ", $rxhdr));

# Receiver data record
my $rxrcd = (  pack( "c", length( $mycall)) .
               pack( "A*", $mycall) .
               pack( "c", length( $mygrid)) .
               pack( "A*", $mygrid) .
               pack( "c", length( $decsw)) .
               pack( "A*", $decsw)
             );

# Determine record length and calculate padding to multiple of 4 bytes
my $rxrcdlen = length( $rxrcd)+ 4;
my $rxrcdpad = 4 - ( $rxrcdlen % 4);

# pack header, data record and padding into complete record
$rxrcd = ( pack( "H*", $rxhdr) .
           pack( "n", ( $rxrcdlen + $rxrcdpad)) .
           $rxrcd . 
           pack( "x$rxrcdpad")
          );

# Sender data header
my $txhdr = "99 93 ";

# pack txhdr into byte stream
$txhdr = join( "", split(" ", $txhdr));

# Sender record, length and padding
my $txrcd;
my $txrcdlen;
my $txrcdpad;

# FT8 fields from FT8 decoder log file
my $gmt;
my $x;
my $snr;
my $dt;
my $tone;
my $freq;
my @rest;

my $ft8msg;
my $time;
my $call;
my $grid;

# holds one single log file line
my $line;

# we're only supporting FT8
my $mode = "FT8";

# outgoing UDP datagram packet to be sent to PSKReporter
my $packet;

# Running sequence number for datagrams
my $seq = 1;

# hash of deduplicated unique calls per band (key is call + band)
my %db;

# call+band key for %db hash
my $cb;

# minute counter to buffer decode lines
my $min = 0;

# lookup table to determine base band FT8 frequency used to calculate Hz offset
my %basefrq = ( 
  "184" => 1840000,
  "357" => 3573000,
  "535" => 5357000,
  "707" => 7074000,
  "1013" => 10136000,
  "1407" => 14074000,
  "1810" => 18100000,
  "2107" => 21074000,
  "2491" => 24915000,
  "2807" => 28074000,
  "5031" => 50313000
);

# unique band key for hash array above
my $base;

# decode counter
my $d = 0;

# datagram size in bytes
my $ds;

$| = 1;

# setup tail to watch FT8 decoder log file and pipe for reading
# 193245 1 0 1  0   0.0   0.0  29.0  -2  0.31 14076009 K1HTV K1RA FM18
# open( LOG, "< /dev/shm/decode-ft8.log");
open( LOG, "< $logfile");

# jump to end of file
seek LOG, 0, 2;

FOREVER:
# Loop forever
while( 1) {

# read in lines from FT8 decoder log file 
READ:
  while( $line = <LOG>) {
# check to see if this line says Decoding (end of minute for FT8 decoder)
    if( $line =~ /^Decoding/) { 
# yes - keep track of minutes data in hash array
      $min++;
      
      next READ;
    }
    
# check if this is a valid FT8 decode line beginning with 6 digit time stamp    
    if( ! ( $line =~ /^\d{6}\s/) ) { 
# no - go to read next line from decoder log
      next READ; 
    }
    
#    163144   4 -0.9 2431 14074  KK5ZV VE5TLW R-16
# looks like a valid line split into variable fields
    ($gmt, $snr, $dt, $tone, $freq, @rest)= split( " ", $line);

    $freq = $freq * 1000 + $tone;
    
# get UNIX time since epoch  
    $time = time();
    
# determine base frequency key for hash lookup into FT8 base band frequency array
    $base = int( $freq / 10000);

# make freq an integer  
    $freq += 0;

# make the FT8 message by appending remainder of line into one variable, space delimited  
    $ft8msg = join( " ", @rest);
  
# Here are all the various FT8 message scenarios we will recognize, extract senders CALL & GRID
# CQ CALL LLnn 
    if( $ft8msg =~ /^CQ\s([\w\d\/]{3,})\s(\w\w\d\d)/) {
      $call = $1;
      $grid = $2;
# CQ [NA,DX,xx] CALL LLnn  
    } elsif ( $ft8msg =~ /^CQ\s\w{2}\s([\w\d\/]{3,})\s(\w\w\d\d)/) {
      $call = $1;
      $grid = $2;  
# CALL1 CALL2 [R][-+]nn
    } elsif ( $ft8msg =~ /^[\w\d\/]{3,}\s([\w\d\/]{3,})\sR*[\-+][0-9]{2}/) {
      $call = $1;
      $grid = "";
# CALL1 CALL2 RRR
    } elsif ( $ft8msg =~ /^[\w\d\/]{3,}\s([\w\d\/]{3,})\sRRR/) {
      $call = $1;
      $grid = "";
# CALL1 CALL2 RR73 or 73
    } elsif ( $ft8msg =~ /^[\w\d\/]{3,}\s([\w\d\/]{3,})\sR*73/) {
      $call = $1;
      $grid = "";
# CALL1 CALL2 GRID
    } elsif ( $ft8msg =~ /^[\w\d\/]{3,}\s([\w\d\/]{3,})\s(\w\w\d\d)/) {
      $call = $1;
      $grid = $2;
    } else {
      next READ;
    }

# does the call have at least one number in it
    if( ! ( $call =~ /\d/) ) { 
# no - maybe be this is a TNX, NAME, QSL message, so skip this line
      next READ; 
    }
    
# have we NOT seen this call on this band yet
    if( ! defined( $db{$call.$base}) ) { 
# yes - save it to hash array
      $db{$call.$base} = $time.",".$call.",".$grid.",".$freq.",".$snr;

# keep count of unique FT8 call+base decodes in hash array for this time window
      $d++;
    } else {
# no - we have seen before, so did we get a grid this decode
      if( $grid ne "") {
# yes - resave decode with grid just in case we didn't before
        $db{$call.$base} = $time.",".$call.",".$grid.",".$freq.",".$snr;
      }
    }  

  } # end of while( $line = <LOG>)
  
  sleep 1;
# reset EOF flag
  seek LOG, 0, 1;  
    
# check if we have exceeded minimum reporting time
  if( ( $min >= $MINTIME) ) {

# yes - prepare to send decodes to PSKReporter, reset datagram sent size counter
    $ds = 0;

# wait random time (0-15 secs) before sending datagram
    sleep( int( rand( 15)));

DECODES:
# loop until all decodes in hash array are packed and sent in datagrams
    while( $d > 0) {
  
      undef $packet;
      undef $txrcd;
  
# loop thru all call+base keys and pack buffered decodes into datagram
      foreach $cb (sort ( keys %db)) {
# split hash into individual variable fields
        ( $time, $call, $grid, $freq, $snr) = split( ",", $db{$cb} );

# build a sender record for this FT8 decoded message 
        $txrcd .= ( pack( "c", length( $call)) .
                    pack( "A*", $call) .
                    pack( "N", $freq) .
                    pack( "c", $snr) .
                    pack( "c", 3) .
                    pack( "A*", "FT8") .
                    pack( "c", 1) .
                    pack( "c", length( $grid)) .
                    pack( "A*", $grid) .
                    pack( "N", $time)
                  );

# remove this FT8 decode from hash array
        delete $db{ $cb};
        
# decrement FT8 main decode counter
        $d--;

# track size of UDP datagram of all FT8 decodes to be sent and test if full reached max limit
# if yes - exit loop to wrap and send datagram
        if( ( length( $txrcd) ) >= $MAXDATA) { last; }
      } # end hash loop to build datagram

# reset datagram size counter in bytes
      $ds = 0;
      
# calculate the length of the record and determine padding to multiple of 4 bytes  
      $txrcdlen = length( $txrcd)+ 4;
      $txrcdpad = 4 - ( $txrcdlen % 4);

# create entire sender record with sender header and 00 padding
      $txrcd = ( pack( "H*", $txhdr) .
                 pack( "n", ( $txrcdlen + $txrcdpad)) .
                 $txrcd .
                 pack( "x$txrcdpad")
                );

# create complete UDP datagram packet holding header, time, sequence number, random ID, 
# receive & send descriptions and receive & sender records
      $packet = ( pack( "H*", $header) .
                  pack( "n", length( $rcvr) + length( $sndr) + length( $rxrcd) + length( $txrcd) + 16) .
                  pack( "N", $time) .
                  pack( "N", $seq++) .
                  pack( "A*", $rid) .
                  pack( "A*", $rcvr) .
                  pack( "A*", $sndr) .
                  pack( "A*", $rxrcd) .
                  pack( "A*", $txrcd)
                 );

# open UDP socket to PSKReporter  
      my $sock = IO::Socket::INET->new(
        Proto    => 'udp',
        PeerPort => $peerport,
        PeerAddr => $peerhost,
      ) or next DECODES ;
#      ) or die "Could not create socket: $!\n";
    
# send datagram
      print $sock $packet;

# close socket
      $sock->close();

    } # end of datagram creation/sending, loop if more FT8 decodes need to be sent in another datagram
    
# reset timer, decode coutner and clear hash array, packet and sender record buffers
    $min = 0;
    undef %db;
    
  } # end of exceed buffer or time to send
          
} # repeat forever
