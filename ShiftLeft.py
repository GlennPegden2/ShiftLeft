
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

    pathlib.Path('/tmp/shiftleft').mkdir(parents=True, exist_ok=True) 
    pathlib.Path('/tmp/shiftleft/dl').mkdir(parents=True, exist_ok=True) 
    pathlib.Path('/tmp/shiftleft/source').mkdir(parents=True, exist_ok=True) 
    pathlib.Path('/tmp/shiftleft/results').mkdir(parents=True, exist_ok=True) 


    print("Downloading URL:" +dlurl)
    urllib.request.urlretrieve(dlurl,'/tmp/shiftleft/dl/wp_tmp.zip')

    print("unzipping")
    with zipfile.ZipFile ('/tmp/shiftleft/dl/wp_tmp.zip') as zf:
        zf.extractall('/tmp/shiftleft/source/')
    return

def scan_static_PHPCS():

    print("Running static analysis using PHP Code Sniffer (with Security Rules)")
    for filename in os.listdir('/tmp/shiftleft/source/'):
        sourcefolder = '/tmp/shiftleft/source/' + filename
        if os.path.isdir('/tmp/shiftleft/source/' + filename) == True:
            print("Running php code sniffer on " + sourcefolder)
            subprocess.getoutput("~/ShiftLeft/tools/phpcs-security-audit/vendor/bin/phpcs --standard=~/ShiftLeft/tools/phpcs-security-audit/example_base_ruleset.xml " + sourcefolder + " > /tmp/shiftleft/results/phpcs.txt")  

def scan_dynamic_burp():
    print("Running dynamic analysis using Burp Pro (this can take a while!)")
    cdir = os.getcwd()
    os.chdir("/tmp/shiftleft/results")
    subprocess.getoutput('java -jar -Xmx1024m -Djava.awt.headless=true  /Applications/Burp\ Suite\ Professional.app/Contents/java/app/burp/burpsuite_pro_1.7.33-18.jar http 127.0.0.1 8088 /')
    os.chdir(cdir)

def standupWordPress():
    print("Running WordPress Docker container")
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml up -d")

def configureWP(pluginName):
    print("Configuring WordPress - Initial Setup")
    passwd=''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli core install --url=http://127.0.0.1:8088 --title=Test --admin_user=admin --admin_password="+passwd+" --admin_email=test@test.com")
#    print("SB1 "+out)
    print("Configuring WordPress - Initialling Plugin")
    out=subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml run --rm my-wpcli plugin install "+pluginName+" --activate")
    print("SB2 "+out)
    print("If all went well, WP should now be running on http://127.0.0.1:8088 the admin password is "+passwd)

def closedownWordPress():
    print("Shutting down WordPress docker container")
    subprocess.getoutput("docker-compose -f ~/ShiftLeft/wpdocker/docker-compose.yaml down --volumes")    

pluginName = "wordpress-seo"

#Cleanup during testing, normally the closedown would run after all the tests had finished
closedownWordPress()

downloadWPPlugin(pluginName)
scan_static_PHPCS()
standupWordPress()

for number in range(12):
    s = subprocess.getoutput("docker ps")
    if s.find("wpdocker_my-wp_1") != -1:
        time.sleep(10) #Give the actual host time to boot
        configureWP(pluginName)
        break
    else:
        print("WP not started yet, lets wait a little longer")
        time.sleep(10)

#We should probably check here if it did ever start
scan_dynamic_burp()

#closedownWordPress()


