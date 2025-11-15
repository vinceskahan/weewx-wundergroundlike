
## WundergroundLike extension for weewx
This extension uploads archive data (only) in Weather Underground format to a specified remote server_url.   This is intended to permit users to send WU-like data to a custom server 'as well as' to the actual Weather Underground.   You only need this extension if you want to do both.

Notes:
* Weather Underground 'rapidfire' to a custom url is 'not' supported here, and is actually disabled in this code
* this extension requires python3

#### For users who only want to upload to Weather Underground
You do not need this extension.  Use the [[Wunderground]] section in weewx.conf to use the uploader that comes with weewx.

#### For users who only want to upload to a custom WeatherUnderground-like site
You do not need this extension.  Add a custom server_url definition to the [[Wunderground] section in weewx.conf to use the uploader that comes with weewx.

#### For users who want to upload to Weather Underground 'and' also a site using the same kind of expected data
You need this extension.  See below for how to install and configure.

----

### Install via the extension installer

* if you are running a pip install, activate your venv first
* use the weewx extension installer to install this extension
   * For weewx v5 users - see [weectl](https://www.weewx.com/docs/5.2/utilities/weectl-extension/) for detailed instructions
   * For weewx v4 users - see [wee_extension](https://www.weewx.com/docs/4.10/utilities.htm\#wee_extension_utility) for detailed instructions
* edit the WundergroundLike stanza in weewx.conf to set your parameters
* restart weewx
* check your syslogs to make sure things are working


### Example installation

````


````

### Credits
This extension is derived (with thanks) from restx.py in weewx 5.2.0 with the
installer modified from the weewx-belchertown skin.  Thanks to:
* Tom Keffer
* Pat O'Brien

