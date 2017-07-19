#!/usr/bin/env perl
use strict;
use warnings;
use POSIX;
use Term::Size;

# Print centered subroutine
sub print_centered {
    my ($string, $width, $char) = @_;
    my $width_of_string = length($string);
    my $adjusted = ceil($width / 2) - ceil($width_of_string / 2);
    if ($adjusted % 2 != 0) {
        $adjusted -= 1;
    }
    my $formatted = $char x $adjusted . " " . $string . " " . $char x $adjusted;
    if (length($formatted) < $width) {
        my $fix = $formatted . $char x ($width - length($formatted));
    }
    elsif (length($formatted) > $width) {
        $formatted = substr($formatted, 0, -(length($formatted) - $width));
    }
    return $formatted . "\n";
}

# Need the terminal size
my ($width, $height) = Term::Size::chars *STDOUT{IO};
if (not $width) {
    $width = 140;
}

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
    # Get SUs from crc-bank.py
    my $line = `/absolute/path/crc-sus.py $account`;
    my @sp = split(' ', $line);
    my $sus = $sp[5];

    # Make everything fit on screen nicely
    my $fourth_term_size = int($width / 4) - 1;
    my $adjusted_width = $fourth_term_size * 4 + 3;

    # Welcome Message
    print('=' x $adjusted_width . "\n");
    print(print_centered("MODIFY Service Unit Usage", $adjusted_width, '-'));
    print('=' x $adjusted_width . "\n");

    # Print Total SUs
    print('-' x $adjusted_width . "\n");
    printf("Total SUs: %${\($adjusted_width - 11)}i\n", $sus);
    print('-' x $adjusted_width . "\n");

    if ($sus == 0) {
        print(print_centered("Your account has no SUs on this cluster", $adjusted_width, ' '));
        print('-' x $adjusted_width . "\n");
    }
    elsif ( $sus == -1 ) {
        print(print_centered("Your account has unlimited SUs on this cluster", $adjusted_width, ' '));
        print('-' x $adjusted_width . "\n");
    }
    else {
        my @clusters = qw( MODIFY ); # e.g. qw( clus1 clus2 )
        foreach my $cluster (@clusters) {
            printf("Cluster: %${\($adjusted_width - 9)}s\n", $cluster);
            print('-' x $adjusted_width . "\n");

            my @usage = `sshare --all --noheader --format=account%30,user%30,rawusage%30 --accounts=$account --cluster=$cluster`;

            printf("%${\($fourth_term_size)}s %${\($fourth_term_size)}s %${\($fourth_term_size)}s %${\($fourth_term_size)}s\n", "Account", "User", "SUs (CPU Hours)", "Percent of Total");
            printf("%${\($fourth_term_size)}s %${\($fourth_term_size)}s %$    {\($fourth_term_size)}s %${\($fourth_term_size)}s\n", '-' x $fourth_term_size, '-' x $fourth_term_size, '-' x $fourth_term_size, '-' x $fourth_term_size);

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
                printf("%${\($fourth_term_size)}s " x $#sp, @sp[0 .. $#sp - 1]);
                printf("%${\($fourth_term_size)}i ", $sp[-1]);
                printf("%${\($fourth_term_size)}.4f\n", 100 * $sp[-1] / $sus);
            }
            print('-' x $adjusted_width . "\n");
        }
    }
}
else {
    print("Your group doesn't have an account according to Slurm\n");
}
