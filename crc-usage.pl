#!/usr/bin/env perl
use strict;
use warnings;

# Need a begin and end dates, choose the whole year
my $year = `date +%y`;
my $begin = "01/01/" . $year;
my $end = `date +%m/%d/%y`;

# Global account
my $account;

# If user provides an account use that, otherwise use the Slurm default account
my $num_args = $#ARGV + 1;
if ($num_args > 1) {
    # Not an acceptable number of arguments, die
    die "ERROR: Usage, crc-usage.pl [optional account]\n";
}
elsif ($num_args == 1) {
    # User provided an account, check it exists in slurm
    $account = `sacctmgr -n list account account=$ARGV[0] format=account%30`;
    chomp $account;
    $account =~ s/^\s+//;
    # If it exists, set it
    if (length($account) != 0) {
        $account = $ARGV[0];
    }
}
else {
    # Use default Slurm account
    use Env qw(USER);
    $account = `sacctmgr -n list user $USER format=defaultaccount%30`;
    chomp $account;
    $account =~ s/^\s+//;
}

if (length($account) != 0) {
    my @clusters = qw( cluster );
    foreach my $cluster (@clusters) {
        # Get SUs from crc-bank.py
        my $line = `/absolute/path/to/crc-sus.py $account`;
        my @sp = split(' ', $line);
        my $sus = $sp[5];

        # Print Header
        print('-' x 61 . "\n");
        printf("Cluster: %52s\n", $cluster);
        printf("Total SUs: %50i\n", $sus);
        print('-' x 61 . "\n");

        if ($sus == 0) {
            print("Your account has no SUs on this cluster\n");
        }
        elsif ( $sus == -1 ) {
            print("Your account has unlimited SUs on this cluster\n");
        }
        else {
            my @usage = `sshare --all --noheader --format=account%30,user%30,rawusage%30 --accounts=$account --cluster=$cluster`;

            printf("%30s%3s: %30i\n", "Total SUs (CPU Hours) on ", $cluster, $sus);
            print('-' x 61 . "\n");
            printf("%30s %30s %30s %30s\n", "Account", "User", "SUs (CPU Hours)", "Percent of Total SUs");
            printf("%30s %30s %30s %30s\n", '-' x 30, '-' x 30, '-' x 30, '-' x 30);

            # Loop over usage lines, replace cpu seconds with cpu hours
            # -> with Slurm Clusters you need to start on second line
            for (my $i = 1; $i < @usage; $i++) {
                # Split the line, convert to CPU Hours
                my @sp = split(' ', $usage[$i]);
                $sp[-1] = $sp[-1]  / (60 * 60);
                # Need this line for the total, otherwise columns are incorrect
                if (scalar(@sp) == 2) {
                    splice(@sp, 1, 0, '');
                }
                # Print out the strings, SUs, and Percent of Total
                printf("%30s " x $#sp, @sp[0 .. $#sp - 1]);
                printf("%30i", $sp[-1]);
                printf("%30.4f\n", 100 * $sp[-1] / $sus);
            }
        }
    }
}
else {
    print("Your group doesn't have an account according to Slurm\n");
}
