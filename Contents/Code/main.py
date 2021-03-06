# -*- coding: utf-8 -*-

import json
import urllib

import plex_util
import common_routes
import pagination
import history
from flow_builder import FlowBuilder
from media_info import MediaInfo

@route(PREFIX + '/all_movies')
def HandleAllMovies(page=1):
    return HandleMovies(id='/films/', title="Movies", page=page)

@route(PREFIX + '/new_movies')
def HandleNewMovies(page=1):
    return HandleMovies(id='/films/novinki/', title="New Movies", page=page)

@route(PREFIX + '/all_series')
def HandleAllSeries(page=1):
    return HandleSeries("/serial/", title='Series', page=page)

@route(PREFIX + '/animation')
def HandleAnimation(page=1):
    return HandleMovies(id='/multfilm/', title="Animation", page=page)

@route(PREFIX + '/anime')
def HandleAnime(page=1):
    return HandleMovies(id='/anime/', title="Anime", page=page)

@route(PREFIX + '/tv_shows')
def HandleTvShows(page=1):
    return HandleMovies(id='/dokumentalnyy/', title="TV Shows", page=page)

@route(PREFIX + '/movies')
def HandleMovies(title, id, page=1):
    oc = ObjectContainer(title2=unicode(L(title)))

    response = service.get_movies(path=id, page=page)

    for item in response['items']:
        name = item['name']
        thumb = item['thumb']

        new_params = {
            'id': item['path'],
            'name': item['name'],
            'thumb': item['thumb'],
            'isSerie': item['isSerie']
        }
        oc.add(DirectoryObject(
            key=Callback(HandleMovieOrSerie, **new_params),
            title=plex_util.sanitize(name),
            thumb=plex_util.get_thumb(thumb)
        ))

    pagination.append_controls(oc, response, callback=HandleMovies, id=id, title=title, page=page)

    return oc

@route(PREFIX + '/movie')
def HandleMovie(operation=None, container=False, **params):
    oc = ObjectContainer(title2=unicode(L(params['name'])), user_agent = 'Plex')

    media_info = MediaInfo(**params)

    if 'season' in media_info:
        season = media_info['season']
    else:
        season = None

    if 'episode' in media_info:
        episode = media_info['episode']
    else:
        episode = None

    if season and int(season) > 0 and episode:
        urls = json.loads(urllib.unquote_plus(media_info['id']))
    else:
        urls = service.get_urls(path=media_info['id'])

    if len(urls) == 0:
        return plex_util.no_contents()
    else:
        service.queue.handle_bookmark_operation(operation, media_info)

        metadata_object = FlowBuilder.build_metadata_object(media_type=media_info['type'], title=media_info['name'])

        metadata_object.key = Callback(HandleMovie, container=True, **media_info)

        metadata_object.rating_key = unicode(media_info['name'])
        metadata_object.thumb = media_info['thumb']
        metadata_object.title = media_info['name']

        for url in urls:
            metadata = service.get_metadata(url)

            if 'height' in metadata:
                metadata["video_resolution"] = metadata['height']

            media_object = FlowBuilder.build_media_object(Callback(common_routes.PlayAudio, url=url), metadata)

            metadata_object.items.append(media_object)

        oc.add(metadata_object)

        playlist_url = service.get_serie_playlist_url(params['id'])

        if playlist_url:
            oc.add(DirectoryObject(
                key=Callback(HandleTracks, name=params['name'], playlist_url=playlist_url),
                title='Soundtracks'
            ))

        if str(container) == 'False':
            history.push_to_history(Data, media_info)
            service.queue.append_bookmark_controls(oc, HandleMovie, media_info)

    return oc

@route(PREFIX + '/tracks')
def HandleTracks(name, playlist_url):
    oc = ObjectContainer(title2=unicode(L(name)))

    serie_info = service.get_serie_info(playlist_url)[0]

    oc.title2 = unicode(serie_info['comment'])

    for item in serie_info['playlist']:
        url = item['file'][0]
        name = item['comment']
        format = "mp3"

        new_params = MediaInfo(
            type='track',
            id=url,
            name=name,
            format=format
        )

        oc.add(HandleTrack(**new_params))

    return oc

@route(PREFIX + '/series')
def HandleSeries(id, title, page=1):
    oc = ObjectContainer(title2=unicode(L(title)))

    response = service.get_series(path=id, page=page)

    for item in response['items']:
        new_params = {
            'type': 'serie',
            'id': item['path'],
            'name': item['name'],
            'thumb': item['thumb']
        }

        oc.add(DirectoryObject(
            key=Callback(HandleSerie, **new_params),
            title=plex_util.sanitize(item['name']),
            thumb=plex_util.get_thumb(item['thumb'])
        ))

    pagination.append_controls(oc, response, callback=HandleSeries, id=id, title=title, page=page)

    return oc

@route(PREFIX + '/serie')
def HandleSerie(operation=None, **params):
    oc = ObjectContainer(title2=unicode(params['name']))

    media_info = MediaInfo(**params)

    service.queue.handle_bookmark_operation(operation, media_info)

    playlist_url = service.get_serie_playlist_url(params['id'])
    serie_info = service.get_serie_info(playlist_url)

    for index, item in enumerate(serie_info):
        season = index+1
        season_name = item['comment'].replace('<b>', '').replace('</b>', '')
        episodes = item['playlist']
        rating_key = service.get_episode_url(params['id'], season, 0)

        new_params = {
            'type': 'season',
            'id': params['id'],
            'serieName': params['name'],
            'name': season_name,
            'thumb': params['thumb'],
            'season': season,
            'episodes': json.dumps(episodes)
        }

        oc.add(SeasonObject(
            key=Callback(HandleSeason, **new_params),
            rating_key=rating_key,
            title=plex_util.sanitize(season_name),
            index=int(season),
            thumb=plex_util.get_thumb(params['thumb'])
        ))

    service.queue.append_bookmark_controls(oc, HandleSerie, media_info)

    return oc

@route(PREFIX + '/season', container=bool)
def HandleSeason(operation=None, container=False, **params):
    oc = ObjectContainer(title2=unicode(params['name']))

    media_info = MediaInfo(**params)

    service.queue.handle_bookmark_operation(operation, media_info)

    if not params['episodes']:
        playlist_url = service.get_serie_playlist_url(params['id'])
        serie_info = service.get_serie_info(playlist_url)
        list = serie_info[int(params['season'])-1]['playlist']
    else:
        list = json.loads(params['episodes'])

    for index, episode in enumerate(list):
        episode_name = episode['comment'].replace('<br>', ' ')
        thumb = params['thumb']
        url = episode['file']

        new_params = {
            'type': 'episode',
            'id': json.dumps(url),
            'name': episode_name,
            'serieName': params['serieName'],
            'thumb': thumb,
            'season': params['season'],
            'episode': episode,
            'episodeNumber': index+1
        }

        key = Callback(HandleEpisode, container=container, **new_params)

        oc.add(DirectoryObject(
            key=key,
            title=unicode(episode_name),
            thumb=plex_util.get_thumb(thumb)
        ))

    if str(container) == 'False':
        history.push_to_history(Data, media_info)
        service.queue.append_bookmark_controls(oc, HandleSeason, media_info)

    return oc

@route(PREFIX + '/episode')
def HandleEpisode(operation=None, container=False, **params):
    oc = ObjectContainer(title2=unicode(L(params['name'])), user_agent='Plex')

    media_info = MediaInfo(**params)

    if 'season' in media_info:
        season = media_info['season']
    else:
        season = None

    if 'episode' in media_info:
        episode = media_info['episode']
    else:
        episode = None

    if season and int(season) > 0 and episode:
        urls = json.loads(urllib.unquote_plus(media_info['id']))
    else:
        urls = service.get_urls(path=media_info['id'])

    if len(urls) == 0:
        return plex_util.no_contents()
    else:
        service.queue.handle_bookmark_operation(operation, media_info)

        metadata_object = FlowBuilder.build_metadata_object(media_type=media_info['type'], title=media_info['name'])

        metadata_object.key = Callback(HandleEpisode, container=True, **media_info)

        metadata_object.rating_key = unicode(media_info['name'])
        metadata_object.thumb = media_info['thumb']
        metadata_object.title = media_info['name']

        for url in urls:
            metadata = service.get_metadata(url)

            if 'height' in metadata:
                metadata["video_resolution"] = metadata['height']

            media_object = FlowBuilder.build_media_object(Callback(common_routes.PlayAudio, url=url), metadata)

            metadata_object.items.append(media_object)

        oc.add(metadata_object)

        if str(container) == 'False':
            history.push_to_history(Data, media_info)
            service.queue.append_bookmark_controls(oc, HandleEpisode, media_info)

    return oc

@route(PREFIX + '/tops')
def HandleTops():
    oc = ObjectContainer(title2=unicode(L('Top')))

    genres = service.get_grouped_genres()['top']

    for genre in genres:
        path = genre['path']
        name = genre['name']

        if path == '/podborka.html':
            oc.add(DirectoryObject(
                key=Callback(HandleTags, name=name),
                title=plex_util.sanitize(unicode(L(name)))
            ))
        else:
            oc.add(DirectoryObject(
                key=Callback(HandleCriteria, id=path, name=name),
                title=plex_util.sanitize(unicode(L(name)))
            ))

    return oc

@route(PREFIX + '/tags')
def HandleTags(name):
    oc = ObjectContainer(title2=unicode(L(name)))

    response = service.get_tags()

    for item in response:
        name = item['name']
        thumb = item['thumb']

        new_params = {
            'id': item['path'],
            'title': item['name']
        }
        oc.add(DirectoryObject(
            key=Callback(HandleMovies, **new_params),
            title=plex_util.sanitize(name),
            thumb=plex_util.get_thumb(thumb)
        ))

    return oc

@route(PREFIX + '/criteria', page=int, per_page=int)
def HandleCriteria(id, name, page=1, per_page=25):
    oc = ObjectContainer(title2=unicode(L(name)))

    response = service.get_movies_by_criteria_paginated(path=id, page=page, per_page=per_page)

    for item in response['items']:
        name = item['name'] + " - " + item['rating']

        new_params = {
            'id': item['path'],
            'name': item['name'],
            'thumb': 'thumb'
        }
        oc.add(DirectoryObject(
            key=Callback(HandleMovieOrSerie, **new_params),
            title=name
        ))

    pagination.append_controls(oc, response, callback=HandleCriteria, id=id, name=name, page=page, per_page=per_page)

    return oc

@route(PREFIX + '/all_genres')
def HandleAllGenres():
    oc = ObjectContainer(title2=unicode(L('Top')))

    grouped_genres = service.get_grouped_genres()

    movies_genres = grouped_genres['films']
    series_genres = grouped_genres['serial']
    anime_genres = grouped_genres['anime']

    oc.add(DirectoryObject(
        key=Callback(HandleGenres, name='Movies', genres=movies_genres),
        title=plex_util.sanitize(unicode(L('Movies')))
    ))

    oc.add(DirectoryObject(
        key=Callback(HandleGenres, name='Series', genres=series_genres),
        title=plex_util.sanitize(unicode(L('Series')))
    ))

    oc.add(DirectoryObject(
        key=Callback(HandleGenres, name='Anime', genres=anime_genres),
        title=plex_util.sanitize(unicode(L('Anime')))
    ))

    return oc

@route(PREFIX + '/genres', genres=list)
def HandleGenres(name, genres):
    oc = ObjectContainer(title2=unicode(L(name)))

    for genre in genres:
        oc.add(DirectoryObject(
            key=Callback(HandleMovies, id=genre['path'], title=genre['name']),
            title=plex_util.sanitize(unicode(L(genre['name'])))
        ))

    return oc

@route(PREFIX + '/track')
def HandleTrack(container=False, **params):
    media_info = MediaInfo(**params)

    url = media_info['id']

    if 'm4a' in media_info['format']:
        format = 'm4a'
    else:
        format = 'mp3'

    metadata = FlowBuilder.get_metadata(format)

    metadata_object = FlowBuilder.build_metadata_object(media_type=media_info['type'], title=media_info['name'])

    metadata_object.key = Callback(HandleTrack, container=True, **media_info)
    metadata_object.rating_key = unicode(media_info['name'])

    if 'thumb' in media_info:
        metadata_object.artist = media_info['thumb']

    if 'artist' in media_info:
        metadata_object.artist = media_info['artist']

    media_object = FlowBuilder.build_media_object(Callback(common_routes.PlayAudio, url=url), metadata)

    metadata_object.items.append(media_object)

    if container:
        oc = ObjectContainer(title2=unicode(params['name']))

        oc.add(metadata_object)

        return oc
    else:
        return metadata_object

@route(PREFIX + '/search')
def HandleSearch(query=None, page=1):
    oc = ObjectContainer(title2=unicode(L('Search')))

    response = service.search(query=query, page=page)

    for item in response['items']:
        name = item['name']
        thumb = item['thumb']

        new_params = {
            'id': item['path'],
            'title': name,
            'name': name,
            'thumb': thumb,
            'isSerie': item['isSerie']
        }
        oc.add(DirectoryObject(
            key=Callback(HandleMovieOrSerie, **new_params),
            title=unicode(name),
            thumb=plex_util.get_thumb(thumb)
        ))

    pagination.append_controls(oc, response, callback=HandleSearch, query=query, page=page)

    return oc

@route(PREFIX + '/movie_or_serie')
def HandleMovieOrSerie(**params):
    if 'isSerie' in params and str(params['isSerie']) == 'True':
        params['type'] = 'serie'
    else:
        params['type'] = 'movie'

    return HandleContainer(**params)

@route(PREFIX + '/container')
def HandleContainer(**params):
    type = params['type']

    if type == 'movie':
        return HandleMovie(**params)
    elif type == 'episode':
        return HandleEpisode(**params)
    elif type == 'season':
        return HandleSeason(**params)
    elif type == 'serie':
        return HandleSerie(**params)

@route(PREFIX + '/queue')
def HandleQueue():
    oc = ObjectContainer(title2=unicode(L('Queue')))

    service.queue.handle_queue_items(oc, HandleContainer, service.queue.data)

    if len(service.queue.data) > 0:
        oc.add(DirectoryObject(
            key=Callback(ClearQueue),
            title=unicode(L("Clear Queue"))
        ))

    return oc

@route(PREFIX + '/clear_queue')
def ClearQueue():
    service.queue.clear()

    return HandleQueue()

@route(PREFIX + '/history')
def HandleHistory():
    history_object = history.load_history(Data)

    oc = ObjectContainer(title2=unicode(L('History')))

    if history_object:
        data = sorted(history_object.values(), key=lambda k: k['time'], reverse=True)

        service.queue.handle_queue_items(oc, HandleContainer, data)

    return oc
