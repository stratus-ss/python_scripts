class Nagios:

    @staticmethod
    def set_downtime(**nagios_options):
        import os
        os.popen("%s -H")
        host_downtime = "[baseUrl]/cmd.cgi?cmd_typ=55&cmd_mod=2&host=[hostname]&com_author=[user]&com_data=[comment]" \
                        "&trigger=0&start_time=[start_time]&end_time=[end_time]&fixed=1&childoptions=1&btnSubmit=Commit"
        cancel_host_downtime = "[baseUrl]/cmd.cgi?cmd_typ=78&cmd_mod=2&down_id=[downtime_id]&btnSubmit=Commit"
        nagios_success = "Your command request was successfully submitted to Nagios for processing"
        nagios_auth_fail = "Sorry, but you are not authorized to commit the specified command."
        webServer = sys.argv[1]
        basePath = "/nagios/cgi-bin"
        baseUrl = "http://" + webServer + ":" + basePath

        url = get_url("host_downtime", {
                baseUrl    => $baseUrl,
                hostname   => uc($hostname),
                user       => $user,
                password   => $userPw,
                comment    => $downtimeComment,
                start_time => $start,
                end_time   => $end,
                duration   => $downtimeDuration,
            }
        # Append the script internal downtime id when id storing is enabled
        # The downtime ID is important to identify the just scheduled downtime for
        # later removal. The CGIs do not provide the downtime id right after sending
        # the schedule request. So it is important to tag the downtime with this.
        storeDowntimeIds = 1
        downtimeId = time
        downtimeComment = " (ID:" + downtimeId


        # Calculate the start of the downtime
        start = datetime.datetime.now())
        downtimeDuration = sys.argv[2]
        # Calculate the end of the downtime
        end = start + (downtimeDuration*60)

        def delDowntimeId:
            my $internalId = shift;

            file = downtimePath + '/'
            file = uc($hostname) + '.txt'

            if os.path.isfile(file)
                if(open(IN, "<", $file))
                    my @contents = <IN>
                    close(IN)

                    @contents = grep { !/^$internalId$/i } @contents

                    if(open(OUT, ">", $file))
                        print OUT @contents
                        close OUT


        sub getDowntimeIds {
            my @arr = ();

            my $file = $downtimePath.'/';
            if($downtimeType == 1) {
                $file .= uc($hostname).'.txt';
            } else {
                $file .= $hostname.'-'.$service.'.txt';
            }

            if(-f $file) {
                if(open(DAT, "<".$file)) {
                    while(my $line = <DAT>) {
                        # Do some validation
                        if($line =~ m/[0-9]+/i) {
                            chomp($line);
                            push(@arr, $line);
                        }
                    }

                    close(DAT);
                } else {
                    error("Could not open temporary file (".$file.").");
                }
            }

            return \@arr;
        }

        sub saveDowntimeId {
            my $file = $downtimePath.'/';
            if($downtimeType == 1) {
                $file .= uc($hostname).'.txt';
            } else {
                $file .= $hostname.'-'.$service.'.txt';
            }

            if(open(DAT, ">>".$file)) {
                print DAT "\n$downtimeId";
                close(DAT);
            } else {
                error("Could not write downtime to temporary file (".$file.").");
            }
        }

        sub getNagiosDowntimeId {
            my $internalId = shift;

            # Get all downtimes
            my @aDowntimes = @{getAllDowntimes()};

            # Filter the just scheduled downtime
            for my $i ( 0 .. $#aDowntimes ) {
                # Matching by:
                #  - internal id in comment field
                #  - triggerId: N/A
                if($aDowntimes[$i]{'triggerId'} eq 'N/A' && $aDowntimes[$i]{'comment'} =~ m/\(ID:$internalId\)/) {

                    debug("Found matching downtime (Host: ".$aDowntimes[$i]{'host'}.", "
                         ."Service: ".$aDowntimes[$i]{'service'}.", Entry-Time: ".$aDowntimes[$i]{'entryTime'}.", "
                         ."Downtime-Id: ".$aDowntimes[$i]{'downtimeId'}.")");
                    return $aDowntimes[$i]{'downtimeId'};
                }
            }

            return "";
        }

        sub deleteDowntime {
            my $nagiosDowntimeId = shift;

            if($downtimeType == 1) {
                # Host downtime
                $url = get_url("del_host_downtime", {
                    baseUrl     => $baseUrl,
                    user        => $user,
                    password    => $userPw,
                    downtime_id => $nagiosDowntimeId,
                });
            } else {
                # Service downtime
                $url = get_url("del_service_downtime", {
                    baseUrl     => $baseUrl,
                    user        => $user,
                    password    => $userPw,
                    downtime_id => $nagiosDowntimeId,
                });
            }