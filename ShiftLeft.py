
import urllib.request
import sys
import re

def downloadWPPlugin (pluginName):
    if not re.match("^[a-z_-]*$", pluginName):
        print("Error! invalid chars in plugin name")
        sys.exit()

    pluginpage = "https://wordpress.org/plugins/" + pluginName + "/"
    response = urllib.request.urlopen(pluginpage)
    html = response.read()
    htmlstr = html.decode("utf-8")
#    url=re.search("\"d(own)loadUrl\":\\s\"(.+?)\",",htmlstr,re.IGNORECASE)
    url=re.search('"downloadUrl":\\s"(.+?)",',htmlstr,re.IGNORECASE)
    print(url.group(1))

    return

html = downloadWPPlugin("wordpress-seo")
print(html)