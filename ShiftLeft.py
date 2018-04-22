
import urllib.request
import sys
import re
import ast
import zipfile
import os
import pathlib
import subprocess
import time
import random
import string
import shutil
import tempfile
import io
from pprint import pprint
from zapv2 import ZAPv2
import config as cfg


def downloadWPPlugin (pluginName):
    print("Downloading "+pluginName)
    if not re.match("^[a-z_-]*$", pluginName):
        print("Error! invalid chars in plugin name")
        sys.exit()

    pluginpage = "https://wordpress.org/plugins/" + pluginName + "/"
    response = urllib.request.urlopen(pluginpage)
    html = response.read()
    htmlstr = html.decode("utf-8")
    url=re.search('"downloadUrl":\\s"(.+?)",',htmlstr,re.IGNORECASE)
    dlurl = url.group(1).replace('\/','/')

    #TODO: Probably file location, perms, randomised dl name etc.

    pathlib.Path(tmpFolder+'/dl').mkdir(parents=True, exist_ok=True) 
    pathlib.Path(tmpFolder+'/source').mkdir(parents=True, exist_ok=True) 
    pathlib.Path(tmpFolder+'/results').mkdir(parents=True, exist_ok=True) 

    print("Downloading URL:" +dlurl)
    urllib.request.urlretrieve(dlurl,tmpFolder+'/dl/wp_tmp.zip')

    print("unzipping")
    with zipfile.ZipFile (tmpFolder+'/dl/wp_tmp.zip') as zf:
        zf.extractall(tmpFolder+'/source/')
    return

def scan_static_PHPCS():

    print("Running static analysis using PHP Code Sniffer (with Security Rules)")
    for filename in os.listdir(tmpFolder+'/source/'):
        sourcefolder = tmpFolder+'/source/' + filename
        if os.path.isdir(tmpFolder+'/source/' + filename) == True:
            print("Running php code sniffer on " + sourcefolder)
            subprocess.getoutput("~/ShiftLeft/tools/phpcs-security-audit/vendor/bin/phpcs --standard=~/ShiftLeft/tools/phpcs-security-audit/example_base_ruleset.xml " + sourcefolder + " > "+tmpFolder+"/results/phpcs.txt")  

def scan_dynamic_burp():
    print("Running dynamic analysis using Burp Pro (this can take a while!)")
    cdir = os.getcwd()
    os.chdir(tmpFolder+"/results")
    subprocess.getoutput('java -jar -Xmx1024m -Djava.awt.headless=true  /Applications/Burp\ Suite\ Professional.app/Contents/java/app/burp/burpsuite_pro_1.7.33-18.jar http 127.0.0.1 8088 /')
    os.chdir(cdir)

def scan_dynamic_zap():
    print("Running dynamic analysis using OWASP Zap (this can take a while!)")
    zap = ZAPv2(apikey=cfg.ZAP_API)
    target="http://127.0.0.1:8088"

    print('Accessing target {}'.format(target))
    zap.urlopen(target)
    time.sleep(2)

    print('Spidering target {}'.format(target))
    scanid = zap.spider.scan(target)
    time.sleep(2)
    while (int(zap.spider.status(scanid)) < 100):
        print('Zap Spider progress %: {}'.format(zap.spider.status(scanid)))
        time.sleep(2)

    print ('Spider completed')

    while (int(zap.pscan.records_to_scan) > 0):
        print ('Zap Records to passive scan : {}'.format(zap.pscan.records_to_scan))
        time.sleep(2)

    print ('Passive Scan completed')

    print ('Active Scanning target {}'.format(target))
    scanid = zap.ascan.scan(target)
    while (int(zap.ascan.status(scanid)) < 100):
        print ('Zap Scan progress %: {}'.format(zap.ascan.status(scanid)))
        time.sleep(5)

    print ('Active Scan completed')
    zaplog=open(tmpFolder+"/results/Zap.log","w")
    pprint(zap.core.alerts(),zaplog)
    zaplog.close()

def scan_dynamic_nikto():
    print("Running dynamic scan using nikto")
    proc = subprocess.Popen("nikto -host 127.0.0.1 -port 8088 -ask no -Format htm -nointeractive -o "+tmpFolder+"/results/nikto.txt", shell=True, stdout=subprocess.PIPE)
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):  # or another encoding
        print(line)

def scan_dynamic_wpscan():
    print("Running dynamic scan using WPScan")
    #There is probably a better option that using /private for this mapping
    out=subprocess.getoutput("docker run -it  --net=shiftleft -v /private/"+tmpFolder+"/results/wpscan.txt:/wpscan/output.txt --rm wpscanteam/wpscan -u http://127.0.0.1:8088 --log /wpscan/output.txt")
    print(out)

def standupWordPress():
    print("Running WordPress Docker container")
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml up -d")
#    print(out)

def configureWP(pluginName):
    print("Configuring WordPress - Initial Setup")
    passwd=''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli core install --url=http://127.0.0.1:8088 --title=Test --admin_user=admin --admin_password="+passwd+" --admin_email=test@test.com")
#    print("SB1 "+out)
    print("Configuring WordPress - Inistalling Plugin")
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli plugin install "+pluginName+" --activate")
    print("SB2 "+out)
    print("If all went well, WP should now be running on http://127.0.0.1:8088 the admin password is "+passwd)

def closedownWordPress():
    print("Shutting down WordPress docker container")
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml down --volumes")    

def zipLogs(pluginName):
    print("Zipping up logs")
    shutil.make_archive(pluginName, "zip", tmpFolder+"/results")

if (len(sys.argv) > 1):
    pluginName = sys.argv[1]
else:
    pluginName = "wordpress-seo"

#Cleanup during testing, normally the closedown would run after all the tests had finished
closedownWordPress()


tmpFolder=tempfile.mkdtemp()

downloadWPPlugin(pluginName)
scan_static_PHPCS()
standupWordPress()

for number in range(12):
    s = subprocess.getoutput("docker ps")
    if s.find("wpdocker_my-wp_1") != -1:
        time.sleep(10) #Give the actual host time to startup
        configureWP(pluginName)
        break
    else:
        print("WP not started yet, lets wait a little longer")
        time.sleep(10)

#TODO: We should probably check here if it did ever start

#TODO: Command line param to skip this
print("Now is your time to go configure the plugin if it needs it. Just press a key to continue when you're ready to start scanning")
input()

scan_dynamic_nikto()
scan_dynamic_wpscan()
scan_dynamic_burp()
scan_dynamic_zap()

#Save the output into a single zip file
zipLogs(pluginName)

closedownWordPress()

shutil.rmtree(tmpFolder)

