from Plugins.Plugin import PluginDescriptor
from Screens.MessageBox import MessageBox
from twisted.web import server, resource
from twisted.internet import reactor
from twisted.web.server import NOT_DONE_YET
import json
import re
import time

_server_started = False
PLUGIN_NAME = "InputEndpoint"
PORT = 8765
LOGFILE = "/tmp/%s.log" % (PLUGIN_NAME)

class thisPlugin(resource.Resource):
    isLeaf = True

    def render_POST(self, request):
        vid = "-"
        vid_ok = False
        try:
            body = request.content.read()
            data = json.loads(body.decode("utf-8"))
            request.setResponseCode(200)
            request.setHeader(
                b"Content-Type",
                b"application/json; charset=utf-8"
            )
            jsn = {
                "status": "ok",
                "endpoint": request.path.decode("utf-8","replace")
            }
            jsn.update(data)
            if jsn.get("endpoint") == "/ytb":
                vid = data.get("video_id","-")
                if re.match(r"^[A-Za-z0-9_-]{11}$", vid):
                    vid_ok = True
                    if _plugin_session is None:
                        jsn.update({"message": "Geen Enigma2-session beschikbaar."})
                    else:
                        jsn.update({"message": "YouTube wordt gestart."})
                else:
                    jsn.update({"message": "Geen valide aanroep."})
            else:
                jsn.update({"message": "Aanvraag wordt (nog) niet ondersteund."})
            request.write(json.dumps(jsn).encode("utf-8"))
            request.finish()
            if _plugin_session is not None and vid_ok:
                reactor.callLater(
                    0,
                    play_youtube_video,
                    _plugin_session,
                    vid
                )
            return NOT_DONE_YET
        except Exception as error:
            log("fout: %s " % (error))
            request.setResponseCode(400)
            request.setHeader(
                b"Content-Type",
                b"application/json; charset=utf-8"
            )
            return json.dumps({
                "status": "error",
                "message": str(error)
            }).encode("utf-8")
            
def log(message):
    try:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOGFILE, "a") as logfile:
            logfile.write("%s [%s] %s\n" % (timestamp, PLUGIN_NAME, message))
            logfile.flush()
    except Exception:
        pass

def start_server(reason=0, **kwargs):
    global _server_started
    if reason != 0 or _server_started:
        return
    endpoint = thisPlugin()
    site = server.Site(endpoint)
    reactor.listenTCP(
        PORT,
        site,
        interface="0.0.0.0"
    )
    _server_started = True
    log("Gestart op poort %s." % (PORT))

def session_start(reason, session=None, **kwargs):
    global _plugin_session

    if reason == 0 and session is not None:
        _plugin_session = session

def open_plugin(session, **kwargs):
    # pluginmenu call
    session.open(
        MessageBox,
        "%s luistert op poort %s." % (PLUGIN_NAME,PORT),
        type=MessageBox.TYPE_INFO,
        timeout=5
    )

def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name=PLUGIN_NAME,
            description="HTTP-inputserver",
            where=PluginDescriptor.WHERE_PLUGINMENU,
            fnc=open_plugin
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_SESSIONSTART,
            fnc=session_start
        ),
        PluginDescriptor(
            where=PluginDescriptor.WHERE_AUTOSTART,
            fnc=start_server
        )
    ]

def play_youtube_video(session, video_id):
    try:
        from enigma import eServiceReference
        from Components.config import config
        from Plugins.Extensions.YouTube.YouTubeApi import YouTubeApi
        from Plugins.Extensions.YouTube.YouTubeUi import YouTubePlayer
        from Plugins.Extensions.YouTube.YouTubeVideoUrl import YouTubeVideoUrl

        # YouTube-plugin-objecten gebruiken
        ytapi = YouTubeApi(config.plugins.YouTube.refreshToken.value)
        ytdl = YouTubeVideoUrl()

        # Directe afspeel-URL laten ophalen
        video_url = ytdl.extract(video_id, ytapi.get_yt_auth())

        if not video_url:
            log("Geen URL beschikbaar voor video-id: %s." % (video_id))
            return

        enigma2ServiceReference = eServiceReference(int(config.plugins.YouTube.player.value), 0, video_url)
        enigma2ServiceReference.setName(video_id)

        youTubePluginTuple = (
            video_id,  # ID
            "",        # thumbnail URL
            None,      # thumbnail
            video_id,  # titel
            "",        # views
            "",        # duur
            video_url, # video URL
            "",        # beschrijving
            "",        # likes
            "",        # grote thumbnail
            "",        # channel ID
            ""         # datum
        )

        log("YouTube-player openen")
        session.open(YouTubePlayer, service=enigma2ServiceReference, current=youTubePluginTuple)

    except Exception as error:
        log("YouTube-fout: %s" % (repr(error)))
