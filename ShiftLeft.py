
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
from termcolor import colored

VERSION='0.1'

def downloadWPPlugin (pluginName):
    print(colored("Checking plugin "+pluginName,'white',attrs=['bold']))
    if not re.match("^[a-z_-]*$", pluginName):
        print("Error! invalid chars in plugin name")
        sys.exit()

    pluginpage = "https://wordpress.org/plugins/" + pluginName + "/"
    response = urllib.request.urlopen(pluginpage)
    html = response.read()
    htmlstr = html.decode("utf-8")
    url=re.search('"downloadUrl":\\s"(.+?)",',htmlstr,re.IGNORECASE)
    dlurl = url.group(1).replace('\/','/')

    pathlib.Path(tmpFolder+'/dl').mkdir(parents=True, exist_ok=True) 
    pathlib.Path(tmpFolder+'/source').mkdir(parents=True, exist_ok=True) 
    pathlib.Path(tmpFolder+'/results').mkdir(parents=True, exist_ok=True) 

    print("Downloading " +dlurl)
    urllib.request.urlretrieve(dlurl,tmpFolder+'/dl/wp_tmp.zip')

    print("Unzipping " +tmpFolder+'/dl/wp_tmp.zip')
    with zipfile.ZipFile (tmpFolder+'/dl/wp_tmp.zip') as zf:
        zf.extractall(tmpFolder+'/source/')
    return

def scan_static_PHPCS():

    print("Running static analysis using "+colored('PHP Code Sniffer', 'red')+" [with Security Rules] from local install")
    for filename in os.listdir(tmpFolder+'/source/'):
        sourcefolder = tmpFolder+'/source/' + filename
        if os.path.isdir(tmpFolder+'/source/' + filename) == True:
#            print("Running php code sniffer on " + sourcefolder)
            subprocess.getoutput("~/ShiftLeft/tools/phpcs-security-audit/vendor/bin/phpcs --standard=~/ShiftLeft/tools/phpcs-security-audit/example_base_ruleset.xml " + sourcefolder + " > "+tmpFolder+"/results/phpcs.txt")  

def scan_static_sonarqube():
    print('Running static analysis using '+colored('SonarQube', 'red')+' (local client with '+colored('Docker Container', 'blue')+' Scaning Server) ', end='', flush=True)
    cdir = os.getcwd()
    os.chdir(tmpFolder+"/source")
    cmd="/Users/gpe13/ShiftLeft/tools/sonar-scanner/bin/sonar-scanner -Dsonar.projectKey=WPTEST-PHP -Dsonar.sources=. -Dsonar.host.url=http://127.0.0.1:9000  -Dsonar.login=ad7d998a53d72ae326fac622294cfff0d8af1084 | tee "+tmpFolder+"/results/sonarQube.txt" 
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):          
        print(".", end='', flush=True)
#        print(line)
    print("")
    os.chdir(cdir)

def scan_dynamic_burp():
    print("Running dynamic analysis using "+colored('Burp Suite Pro', 'red')+" via Proxy Server (this can take a while!)")
    cdir = os.getcwd()
    os.chdir(tmpFolder+"/results")
    subprocess.getoutput('java -jar -Xmx1024m -Djava.awt.headless=true  /Applications/Burp\ Suite\ Professional.app/Contents/java/app/burp/burpsuite_pro_1.7.33-18.jar http 127.0.0.1 8088 /')
    os.chdir(cdir)

def scan_dynamic_zap():
    print("Running dynamic analysis using "+colored('OWASP ZAP', 'red')+" via Proxy Server")
    zap = ZAPv2(apikey=cfg.ZAP_API)
    target="http://127.0.0.1:8088"

    zap.urlopen(target)

    print('-Zap Spider ', end='', flush=True)
    scanid = zap.spider.scan(target)
    time.sleep(2)
    while (int(zap.spider.status(scanid)) < 100):
        print('.', end='', flush=True)
        time.sleep(2)
    print('')

    print('-Zap Passive Scan', end='', flush=True)
    while (int(zap.pscan.records_to_scan) > 0):
        print ('.', end='', flush=True)
        time.sleep(2)
    print('')

    print ('-Zap Active Scan', end='', flush=True)
    scanid = zap.ascan.scan(target)
    while (int(zap.ascan.status(scanid)) < 100):
        print ('.', end='', flush=True)
        time.sleep(5)
    print('')

    zaplog=open(tmpFolder+"/results/Zap.log","w")
    pprint(zap.core.alerts(),zaplog)
    zaplog.close()

def scan_dynamic_nikto():
    print("Running dynamic analysis using "+colored('Nikto', 'red')+" from local install", end='', flush=True)
    proc = subprocess.Popen("nikto -host 127.0.0.1 -port 8088 -ask no -Format htm -nointeractive -o "+tmpFolder+"/results/nikto.txt", shell=True, stdout=subprocess.PIPE)
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"):  
        print(".", end='', flush=True)
    print("")

def scan_dynamic_wpscan():
    print("Running dynamic analysis using "+colored('WPScan', 'red')+" from "+colored('Docker Container', 'blue'), end='', flush=True)
    cmd="docker run -it  --net=\"host\" -v /private/"+tmpFolder+"/results/:/tmp/wpscan/ --name my-wpscan-live --rm wpscanteam/wpscan -u http://host.docker.internal:8088 --follow-redirection --log /tmp/wpscan/wpscan.txt"
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    for line in io.TextIOWrapper(proc.stdout, encoding="utf-8"): 
        print(".", end='', flush=True)
    print("")

def standupWordPress():
    print("Running WordPress "+colored('Docker Container', 'blue'))
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml up -d")
#    print(out)

def configureWP(pluginName):
    print("Configuring WordPress - Initial Setup via "+colored('Docker Container', 'blue')+" version of wp-cli")
    passwd=''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli core install --url=http://127.0.0.1:8088 --title=Test --admin_user=admin --admin_password="+passwd+" --admin_email=test@test.com")
#    print("SB1 "+out)
    print("Configuring WordPress - Installing Plugin "+colored('Docker Container', 'blue')+" version of wp-cli")
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli plugin install "+pluginName+" --activate")
    print("SB2 "+out)
    print(colored("If all went well, WP should now be running on http://127.0.0.1:8088 the admin password is "+passwd,'white',attrs=['bold', 'underline'])+". \nNote: Password is randomly generated on each run and the container it is for is destroy when the run completes")

def closedownWordPress():
    print("Shutting down WordPress","white")
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml down --volumes")    

def zipLogs(pluginName):
    print("Zipping up logs")
    shutil.make_archive(pluginName, "zip", tmpFolder+"/results")
    cwd=os.getcwd()
    print(colored("You can find all your results in "+cwd+"/"+pluginName+".zip",'white',attrs=['bold', 'underline']))



print("\n\n"+colored("ShiftLeft v"+VERSION,'green'))

if (len(sys.argv) > 1):
    pluginName = sys.argv[1]
else:
    pluginName = "wordpress-seo"

#Cleanup during testing, normally the closedown would run after all the tests had finished
#closedownWordPress()


tmpFolder=tempfile.mkdtemp()
downloadWPPlugin(pluginName)
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
print(colored("Now is your time to go configure the plugin if it needs it. Just press a key to continue when you're ready to start scanning",'yellow'))
#input()

print("Let the scanning begin!")
scan_static_PHPCS()
scan_static_sonarqube()
scan_dynamic_wpscan()
scan_dynamic_nikto()
scan_dynamic_burp()
scan_dynamic_zap()

#Save the output into a single zip file
zipLogs(pluginName)

closedownWordPress()

shutil.rmtree(tmpFolder)

