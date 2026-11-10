# TimeMonitor.py - Windows clock monitor: polls NTP servers with w32tm and writes
# offset, delay and w32time status to InfluxDB.
#
# SPDX-License-Identifier: GPL-3.0-only
# Copyright (C) 2022 Hank Karl
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License only.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import configparser
import os
import subprocess
import socket
import time


# Settings come from config.ini next to this script (copy config.example.ini to start).
# INFLUX_URL, INFLUX_ORG, INFLUX_BUCKET and INFLUX_TOKEN environment variables override the file.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")
if not os.path.exists(CONFIG_FILE):
    CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.example.ini")
    print("config.ini not found: using config.example.ini")
config = configparser.ConfigParser(delimiters=("=",), inline_comment_prefixes=("#", ";"))  # "=" only: IPv6 has ":"
config.optionxform = str          # keep server names as written
if not config.read(CONFIG_FILE):
    raise SystemExit("Can't read " + CONFIG_FILE)

LOOP_SECONDS = config.getfloat("monitor", "loop_seconds", fallback=5)  # poll NTP servers every X seconds

PRIMARY_SERVER_OFFSET = 100000000 # offset limit, >= calls for resync (unused: resync is disabled)

SERVER_ADDRESS = 0
SERVER_POLL_LOOPS = 1  # index into ntp_servers: poll the server every x LOOP_SECONDS periods

# [servers]: name = poll interval in seconds.  The first one is the primary (local) server.
# Server names may only be host names or IPv4/IPv6 addresses.
SERVER_NAME_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-:[]")
ntp_servers = []
for name, seconds in config.items("servers"):
    if not name or name.startswith("-") or not set(name) <= SERVER_NAME_CHARS:
        print("Skipping invalid server name in [servers]:", repr(name))
        continue
    ntp_servers.append([name, max(1, round(float(seconds) / LOOP_SECONDS))])
if not ntp_servers:
    raise SystemExit("No servers listed in [servers] in " + CONFIG_FILE)
PRIMARY_SERVER = ntp_servers[0][SERVER_ADDRESS]



##############################################################################################
#query_source_command = 'cmd /c w32tm /query /source'
# returns error_code, line protocol tags and fields - Stratum=int ReferenceID=0x12345678 ReferenceIP=12.34.56.43 Last Successful Sync Time=  Source=string Poll Interval- string
#########################################################################################
def find_time_source():
    
    return_error = -1
   

    w32tm_command = ['w32tm', '-query', '-status']
    
    #print("\n\n here is the command \n ", w32tm_command, " \n \n")
    
    try:
        w32tm_status = subprocess.check_output(w32tm_command, stderr=subprocess.STDOUT)
    except (subprocess.CalledProcessError, OSError) as e:
        print("w32tm -query -status failed:", e)
        return 1, "", "", "", "", "", ""
    w32tm_status = w32tm_status.decode('utf-8', errors='replace').replace('\r', '')
    #print(w32tm_status)  
    
    ################# stratum calculation ############################################
    stratum_position = w32tm_status.find('Stratum:') 
    if stratum_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(stratum_position, w32tm_status[stratum_position]) 
    w32tm_status = w32tm_status[stratum_position:]
    
    #print(w32tm_status) 
    
    stratum_end = w32tm_status.find(' ',9) 
    #print(w32tm_status[stratum_end:])
    str_stratum = w32tm_status[9:stratum_end]   
        
    stratum_measure = str_stratum    
    #print(stratum_measure) 
    
 
    ################# ReferenceID calculation ############################################
    ref_id_position = w32tm_status.find('ReferenceId:') 
    if ref_id_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(ref_id_position, w32tm_status[ref_id_position])
    w32tm_status = w32tm_status[ref_id_position:]
    
    #print(w32tm_status)
    
    ref_id_end = w32tm_status.find(' ',13) 
    #print(w32tm_status[ref_id_end:])
    str_ref_id = w32tm_status[15:ref_id_end]   
        
    ref_id_measure = str_ref_id    
    #print(ref_id_measure) 

    ################# ReferenceIP calculation ############################################
    ref_ip_position = w32tm_status.find(':') 
    if ref_ip_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(ref_ip_position, w32tm_status[ref_ip_position])
    
    #print(w32tm_status)
    
    ref_ip_start = w32tm_status.find('IP:',2) +5
    ref_ip_end = w32tm_status.find(")")
    #print(w32tm_status[ref_ip_start:ref_ip_end])
    str_ref_ip = w32tm_status[ref_ip_start:ref_ip_end] if ref_ip_start >= 5 else ""  # no IP when the source is a local clock
        
    ref_ip_measure = str_ref_ip    
    #print(ref_ip_measure) 

    ################# Last Successful Sync Time calculation ############################################
    last_sync_position = w32tm_status.find('Time:') 
    if last_sync_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(last_sync_position, w32tm_status[last_sync_position])
    w32tm_status = w32tm_status[last_sync_position:]
    
        
    #print(w32tm_status)
    
    last_sync_start = w32tm_status.find(':') +2
    last_sync_end = w32tm_status.find("\n")
    #print(w32tm_status[last_sync_start:last_sync_end])
    str_last_sync = w32tm_status[last_sync_start:last_sync_end]   
    str_last_sync = str_last_sync.replace(",", "-")
    str_last_sync = str_last_sync.replace(" ", "_")    
        
    last_sync_measure = str_last_sync    
    #print(last_sync_measure) 

    ################# Source calculation ############################################
    clock_source_position = w32tm_status.find('Source:') 
    if clock_source_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(clock_source_position, w32tm_status[clock_source_position])
    w32tm_status = w32tm_status[clock_source_position:]
    
        
    #print(w32tm_status)
    
    clock_source_start = w32tm_status.find(':') +2
    clock_source_end = w32tm_status.find("\n")
    #print(w32tm_status[clock_source_start:clock_source_end])
    str_clock_source = w32tm_status[clock_source_start:clock_source_end]   
    str_clock_source = str_clock_source.replace(",", "-")
        
    clock_source_measure = str_clock_source    
    #print(clock_source_measure) 

    
    ################# Poll Interval calculation ############################################
    poll_position = w32tm_status.find('Interval:') 
    if poll_position <0:
        return_error = 1
        return 1, "", "", "", "", "", ""

    #print(poll_position, w32tm_status[poll_position])
    w32tm_status = w32tm_status[poll_position:]
    
        
    #print(w32tm_status)
    
    poll_start = w32tm_status.find(':') +2
    poll_end = w32tm_status.find("\n")
    #print(w32tm_status[poll_start:poll_end])
    str_poll = w32tm_status[poll_start:poll_end]   
    str_poll = str_poll.replace(",", "-")
        
    poll_measure = str_poll    
    #print(poll_measure) 

    # Store numbers as integers so they graph and filter: "2 (secondary ...)" -> 2, "6 (64s)" -> 6 (log2 seconds)
    try:
        stratum_measure = int(stratum_measure.split()[0])
        poll_measure = int(poll_measure.split()[0])
    except (ValueError, IndexError):
        print("w32tm returned an unreadable stratum or poll interval:", repr(stratum_measure), repr(poll_measure))
        return 1, "", "", "", "", "", ""

    return return_error, stratum_measure, ref_id_measure, ref_ip_measure, last_sync_measure, clock_source_measure, poll_measure


#w32tm_command = 'cmd /c w32tm -stripchart -computer:<server> -samples:1'
#########################################################################################

def find_time_offset_from_server(ntp_server):
    
    return_error = -1
    
    w32tm_command = ['w32tm', '-stripchart', '-computer:' + ntp_server, '-samples:1']
    
    #print("\n\n here is the command \n ", w32tm_command, " \n \n")
    
    try:
        w32tm_stats = subprocess.check_output(w32tm_command, stderr=subprocess.STDOUT, timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        print("w32tm -stripchart failed for", ntp_server, ":", e)
        return 3, 0, 0
    w32tm_stats = w32tm_stats.decode('utf-8', errors='replace').replace('\r', '')
    #print(w32tm_stats)  ######################################################################
    
    ################# delay calculation ############################################
    delay_position = w32tm_stats.find('d:') 
    #assert (delay_position >= 0), "\n\n\nwin32tm didn't return a delay value \n"
    if delay_position <0:
        return_error = 1
        return 1, 0, 0
    #print("delay: ", delay_position, w32tm_stats[delay_position])##################################
    w32tm_stats = w32tm_stats[delay_position:]
    
    #print('w32tm_stats = ', w32tm_stats)#####################################################
    
    delay_end = w32tm_stats.find(' ') 
    str_delay = w32tm_stats[2:delay_end-1]      # get rid of :d before number and unit indicator after it
    delay_unit = w32tm_stats[delay_end-1]       # unit indicator, probably s
    
    if delay_unit != "s":
        print("w32tm returned a delay in units other than seconds from", ntp_server)
        return 4, 0, 0
    
    decimal_pos = str_delay.find('.')
    delay_str_len = len(str_delay)     
        
      
    
 #   num0toAdd = 9 - (delay_str_len - (decimal_pos +1))  # ns to sec - multiply by 10**(9 - the number of digits we have past the decimal point.(
 #   str_delay = str_delay.replace(".","")
 #   delay = int(str_delay)
 #   delay = delay * 10**num0toAdd   # convert string from seconds to nanoseconds - avoid looping by using math
    try:
        delay = float(str_delay)
    except ValueError:
        print("w32tm returned an unreadable delay from", ntp_server, ":", str_delay)
        return 4, 0, 0

    #print ("delay ", delay, "...", delay_unit) ##############################################
    
    ################# offset calculation ############################################
    offset_position = w32tm_stats.find('o:') 
    #assert (offset_position >= 0), "\n\n\nwin32tm didn't return an offset value \n"
    if offset_position < 0:
        return_error = 2
        return 2, 0, 0

    #print("offset: ", offset_position, w32tm_stats[offset_position])##################################
    w32tm_stats = w32tm_stats[offset_position:]
    
    #print('w32tm_stats = ', w32tm_stats)#####################################################
    
    offset_end = w32tm_stats.find(' ') 
    str_offset = w32tm_stats[2:offset_end-1]      # get rid of :d before number and unit indicator after it
    offset_unit = w32tm_stats[offset_end-1]       # unit indicator, probably s
    
    if offset_unit != "s":
        print("w32tm returned an offset in units other than seconds from", ntp_server)
        return 5, 0, 0
    
    decimal_pos = str_offset.find('.')
    offset_str_len = len(str_offset)     
       
      
    
#    num0toAdd = 9 - (offset_str_len - (decimal_pos +1))  # ns to sec - multiply by 10**(9 - the number of digits we have past the decimal point.(
#    str_offset = str_offset.replace(".","")
#    offset = int(str_offset)
#    offset = offset * 10**num0toAdd   # convert string from seconds to nanoseconds - avoid looping by using math
    try:
        offset = float(str_offset)
    except ValueError:
        print("w32tm returned an unreadable offset from", ntp_server, ":", str_offset)
        return 5, 0, 0

#    print ("offset ", offset, "...", offset_unit) ##############################################
    


    #print ("offset = ", offset, " delay = ", delay, "\n")
    return return_error, delay,  offset


######################################################################################################
def find_my_ip_addr():
    # UDP connect sends nothing; it just picks the local address that routes to the primary server.
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect((PRIMARY_SERVER, 123))
            return sock.getsockname()[0]
    except OSError:
        return socket.gethostbyname(socket.gethostname())

##################################################################### This doesn't work.
def resync_time():
    resync_command = 'cmd /c "w32tm /resync"'
    x = ['cmd /c w32tm /monitor']
    retval = subprocess.check_output('cmd /k w32tm /resync /soft')
    print (retval)
    returnvalue = subprocess.check_output(resync_command)
    print('time resync requested')
    return

############################################################################################################
#
#                                          start main 
#
############################################################################################################

my_ip_addr = find_my_ip_addr()

# InfluxDB 2.x connection settings.  Leave the token empty to just print results.
def influx_setting(name, default=""):
    return os.environ.get("INFLUX_" + name.upper()) or config.get("influxdb", name, fallback=default)

url    = influx_setting("url", "http://localhost:8086")
org    = influx_setting("org")
bucket = influx_setting("bucket", "ClockMetrics")
token  = influx_setting("token")
influx_writer = None
if token:
    import influxdb_client
    from influxdb_client.client.write_api import SYNCHRONOUS
    client = influxdb_client.InfluxDBClient(url=url, token=token, org=org, verify_ssl=False, debug=False)
    influx_writer = client.write_api(write_options=SYNCHRONOUS)
    print("Writing to InfluxDB", url, "bucket", bucket, "as measurement", my_ip_addr)
else:
    print("INFLUX_TOKEN not set: printing results only.")


def write_point(p):
    try:
        influx_writer.write(bucket=bucket, org=org, record=p)
    except Exception as e:
        print("InfluxDB write failed:", e)


query_count = 0
query_errors = 0


try:
    for loop_count in range(0, 1000000000000):
        start_time = time.monotonic()   # loop timing: immune to clock steps
    
        status_time = time.time_ns()     # InfluxDB timestamp: real time this reading was taken
        return_error, stratum_measure, ref_id_measure, ref_ip_measure, last_sync_measure, clock_source_measure, poll_measure = find_time_source()
        #print(return_error, stratum_measure, ref_id_measure, ref_ip_measure, last_sync_measure, clock_source_measure, poll_measure)
        if (return_error <0):
             print("w32time: stratum", stratum_measure, " source", clock_source_measure, " last sync", last_sync_measure)
        if (return_error <0) and influx_writer:
             ns_time = status_time
             p = influxdb_client.Point(my_ip_addr)\
                        .field("Stratum", stratum_measure)\
                        .field("ReferenceID", ref_id_measure)\
                        .field("ReferenceIP", ref_ip_measure)\
                        .field("LastSync", last_sync_measure)\
                        .field("Source", clock_source_measure)\
                        .field("PollInterval", poll_measure)\
                        .field("PollSeconds", 2 ** poll_measure)\
                        .time(ns_time)
             #print(p)
             write_point(p)

        for ntp_server in ntp_servers:
            if (loop_count%ntp_server[SERVER_POLL_LOOPS]) == 0:
                query_count += 1
                sample_time = time.time_ns()     # real time this server was sampled
                return_error, delay, offset  = find_time_offset_from_server(ntp_server[SERVER_ADDRESS])
                if return_error < 0:
                    print ("NTP Server = ", ntp_server[SERVER_ADDRESS], "  offset = ", offset, " delay = ", delay)
                    if not influx_writer:
                        continue
                    ns_time = sample_time
                    p = influxdb_client.Point(my_ip_addr)\
                        .tag("ReferenceNTPServer", ntp_server[SERVER_ADDRESS])\
                        .field("Offset_s", offset)\
                        .field("Delay_s", delay)\
                        .time(ns_time)
     #               p = influxdb_client.Point("W32Time")\
     #                   .tag("host", my_ip_addr)\
     #                   .tag("ReferenceNTPServer", ntp_server[SERVER_ADDRESS])\
     #                   .field("last_offset", offset)\
     #                   .field("root_delay", delay)\
     #                   .time(ns_time)
                    write_point(p)
                else:
                    print ("loopcount", loop_count, "NTP Server: ", ntp_server[SERVER_ADDRESS], "didn't return a value")
                    query_errors += 1
                    #break
                #if ntp_server[SERVER_ADDRESS] == PRIMARY_SERVER:  # check for primary server
                    #if offset >= PRIMARY_SERVER_OFFSET:
                        #print ("primary server offset too high")
                        #resync_time()

        end_time = time.monotonic()
        loop_duration = end_time - start_time
        #print("start time: ", start_time, "; endtime:", end_time, "; loop_duration: ", loop_duration)
        sleep_time = LOOP_SECONDS - loop_duration;
        if sleep_time < 0:
            print("Warning: took too long: ", loop_duration, " program loops every ", LOOP_SECONDS)
        else:
            time.sleep(sleep_time)
except KeyboardInterrupt:
    print("Stopped.")

print ("total queries = ", query_count, "Errors = ", query_errors)
