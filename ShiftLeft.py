
import urllib.request
import sys
import re
import ast
import zipfile

def downloadWPPlugin (pluginName):
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
    finfo = urllib.request.urlretrieve(dlurl,'tmp/wp_tmp.zip')
    with zipfile.ZipFile ('tmp/wp_tmp.zip') as zf:
        zf.extractall('tmp')



    return

html = downloadWPPlugin("wordpress-seo")
print(html)