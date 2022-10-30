import re
import os
import aigpy
import requests

from bot import LOGGER
from config import Config
from pathvalidate import sanitize_filename
from mutagen.flac import FLAC
from mutagen.mp3 import EasyMP3

from bot.helpers.translations import lang
from bot.helpers.qobuz.qopy import qobuz_api
from bot.helpers.utils.metadata import base_metadata, set_metadata

QL_DOWNGRADE = "FormatRestrictedByFormatAvailability"

async def get_url_info(url):

    """Returns the type of the url and the id.
    Compatible with urls of the form:
        https://www.qobuz.com/us-en/{type}/{name}/{id}
        https://open.qobuz.com/{type}/{id}
        https://play.qobuz.com/{type}/{id}
        /us-en/{type}/-/{id}
    """

    r = re.search(
        r"(?:https:\/\/(?:w{3}|open|play)\.qobuz\.com)?(?:\/[a-z]{2}-[a-z]{2})"
        r"?\/(album|artist|track|playlist|label)(?:\/[-\w\d]+)?\/([\w\d]+)",
        url,
    )
    return r.groups()

async def check_type(url):
    possibles = {
            "playlist": {
                "func": qobuz_api.get_plist_meta,
                "iterable_key": "tracks",
            },
            "artist": {
                "func": qobuz_api.get_artist_meta,
                "iterable_key": "albums",
            },
            "label": {
                "func": qobuz_api.get_label_meta,
                "iterable_key": "albums",
            },
            "album": {"album": True, "func": None, "iterable_key": None},
            "track": {"album": False, "func": None, "iterable_key": None},
        }
    try:
        url_type, item_id = await get_url_info(url)
        type_dict = possibles[url_type]
    except (KeyError, IndexError):
        return

    content = None
    if type_dict["func"]:
        content = [item for item in type_dict["func"](item_id)]
        content_name = content[0]["name"]
        LOGGER.info(
            f"Downloading all the music from {content_name} "
            f"({url_type})!"
        )

        smart_discography = True
        if smart_discography and url_type == "artist":
            # change `save_space` and `skip_extras` for customization
            items = smart_discography_filter(
                content,
                save_space=True,
                skip_extras=True,
            )
        else:
            items = [item[type_dict["iterable_key"]]["items"] for item in content][
                0
            ]

        LOGGER.info(f"{len(items)} downloads in queue")
        return items, None, type_dict, content
    else:
        return None, item_id, type_dict, content


async def download_track(bot, update, id, r_id, u_name, track_meta, path, album_meta=None, 
    f_album=False, type='track'):
    raw_data = qobuz_api.get_track_url(id)
    try:
        url = raw_data['url']
    except KeyError:
        LOGGER.warning('Track not available for download')
        return

    aigpy.net.downloadFile(url, path)
    await set_metadata(path, track_meta)

    if type == 'track' and Config.MENTION_USERS == "True":
        text = lang.select.USER_MENTION_TRACK.format(u_name)
    else:
        text = None

    thumb_path = path + f'_thumbnail.jpg'
    aigpy.net.downloadFile(track_meta['thumbnail'], thumb_path)

    await get_duration(path, track_meta['extention'], track_meta)

    await bot.send_audio(
        chat_id=update.chat.id,
        audio=path,
        caption=text,
        duration=int(track_meta['duration']),
        performer=track_meta['artist'],
        title=track_meta['title'],
        thumb=thumb_path,
        reply_to_message_id=r_id
    )

    os.remove(path)
    os.remove(thumb_path)

async def get_metadata(id, type='track'):
    metadata = base_metadata.copy()
    if type == 'track':
        raw_meta = qobuz_api.get_track_url(id)
        if "sample" not in raw_meta and raw_meta["sampling_rate"]:
            q_meta = qobuz_api.get_track_meta(id)
    elif type == 'album':
        q_meta = qobuz_api.get_album_meta(id)
        if not q_meta["streamable"]:
            return None, None, lang.select.ERR_QOBUZ_NOT_STREAMABLE


    metadata['title'] = q_meta['title']
    metadata['artist'] = await get_artist(q_meta, type)
    try:
        metadata['albumart'] = q_meta['image']['large']
        metadata['thumbnail'] = q_meta['image']['thumbnail']
        metadata['totaltracks'] = q_meta['tracks_count']
        metadata['date'] = q_meta['release_date_original']
    except KeyError:
         metadata['albumart'] = q_meta['album']['image']['large']
         metadata['thumbnail'] = q_meta['album']['image']['thumbnail']
         metadata['totaltracks'] = q_meta['album']['tracks_count']
         metadata['date'] = q_meta['album']['release_date_original']
    if type=='track':
        metadata['isrc'] = q_meta['isrc']
    else:
        raw_meta = q_meta

    return metadata, raw_meta, None

async def get_duration(path, ext, track_meta):
    if ext=='mp3':
        audio = EasyMP3(path)
    else:
        audio = FLAC(path)
    track_meta['duration'] = audio.info.length


async def post_cover(meta, bot, update, r_id, u_name, quality=None):
    post_details = lang.select.QOBUZ_ALBUM_DETAILS.format(
        meta['title'],
        meta['artist'],
        meta['date'],
        meta['totaltracks']
    )

    if quality:
        post_details = post_details + lang.select.QOBUZ_ALBUM_QUALITY_ADDON.format(quality)
    if Config.MENTION_USERS == "True":
            post_details = post_details + lang.select.USER_MENTION_ALBUM.format(u_name)

    await bot.send_photo(
        chat_id=update.chat.id,
        photo=meta['albumart'],
        caption=post_details,
        reply_to_message_id=r_id
    )

async def check_quality(raw_meta, type='track'):
    if int(qobuz_api.quality) == 5:
        return 'mp3'
    if not type=='track':
        raw_meta = raw_meta["tracks"]["items"][0]
        new_track_dict = qobuz_api.get_track_url(raw_meta["id"])
    else:
        new_track_dict = raw_meta

    restrictions = new_track_dict.get("restrictions")
    if isinstance(restrictions, list):
        if any(
            restriction.get("code") == QL_DOWNGRADE
            for restriction in restrictions
        ):
            quality_met = False
    quality = f'{new_track_dict["bit_depth"]}B - {new_track_dict["sampling_rate"]}'

    return "flac", quality

async def get_artist(data, type):
    if type == 'track':
        artists = []
        text = data['performers']
        list = text.split(' - ')
        to_remove = [', ComposerLyricist', ', FeaturedArtist', ', MainArtist', ', Vocal Producer', ', Vocal Engineer', ', AssociatedPerformer', ', StudioPersonnel', ', Producer']
        for item in list:
            if 'MainArtist' in item or 'FeaturedArtist' in item:
                for tag in to_remove:
                    item = item.replace(tag, '')
                artists.append(item)

        return ' '.join([str(artist) for artist in artists])
    elif type == 'album':
        return data['subtitle']

def smart_discography_filter(
    contents: list, save_space: bool = False, skip_extras: bool = False
) -> list:
    """
    :param list contents: contents returned by qobuz API
    :param bool save_space: choose highest bit depth, lowest sampling rate
    :param bool remove_extras: remove albums with extra material (i.e. live, deluxe,...)
    :returns: filtered items list
    """

    TYPE_REGEXES = {
        "remaster": r"(?i)(re)?master(ed)?",
        "extra": r"(?i)(anniversary|deluxe|live|collector|demo|expanded)",
    }

    def is_type(album_t: str, album: dict) -> bool:
        """Check if album is of type `album_t`"""
        version = album.get("version", "")
        title = album.get("title", "")
        regex = TYPE_REGEXES[album_t]
        return re.search(regex, f"{title} {version}") is not None

    def essence(album: dict) -> str:
        """Ignore text in parens/brackets, return all lowercase.
        Used to group two albums that may be named similarly, but not exactly
        the same.
        """
        r = re.match(r"([^\(]+)(?:\s*[\(\[][^\)][\)\]])*", album)
        return r.group(1).strip().lower()

    requested_artist = contents[0]["name"]
    items = [item["albums"]["items"] for item in contents][0]

    # use dicts to group duplicate albums together by title
    title_grouped = dict()
    for item in items:
        title_ = essence(item["title"])
        if title_ not in title_grouped:  # ?
            #            if (t := essence(item["title"])) not in title_grouped:
            title_grouped[title_] = []
        title_grouped[title_].append(item)

    items = []
    for albums in title_grouped.values():
        best_bit_depth = max(a["maximum_bit_depth"] for a in albums)
        get_best = min if save_space else max
        best_sampling_rate = get_best(
            a["maximum_sampling_rate"]
            for a in albums
            if a["maximum_bit_depth"] == best_bit_depth
        )
        remaster_exists = any(is_type("remaster", a) for a in albums)

        def is_valid(album: dict) -> bool:
            return (
                album["maximum_bit_depth"] == best_bit_depth
                and album["maximum_sampling_rate"] == best_sampling_rate
                and album["artist"]["name"] == requested_artist
                and not (  # states that are not allowed
                    (remaster_exists and not is_type("remaster", album))
                    or (skip_extras and is_type("extra", album))
                )
            )

        filtered = tuple(filter(is_valid, albums))
        # most of the time, len is 0 or 1.
        # if greater, it is a complete duplicate,
        # so it doesn't matter which is chosen
        if len(filtered) >= 1:
            items.append(filtered[0])

    return items

def create_and_return_dir(directory):
    fix = os.path.normpath(directory)
    os.makedirs(fix, exist_ok=True)
    return 