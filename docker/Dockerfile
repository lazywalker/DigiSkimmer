ARG VER_BASE="latest"
FROM lazywalker/digiskr-base:${VER_BASE}

LABEL maintainer="Michael BD7MQB <bd7mqb@qq.com>"

COPY settings.py.template /opt/digiskr/settings.py
COPY docker/entrypoint.sh /entrypoint.sh
COPY . /app/digiskr

# set TMP_PATH and LOG_PATH
RUN sed -i -e "s/TMP_PATH = '.*'/TMP_PATH = '\/tmp\/digiskr'/g" /opt/digiskr/settings.py && \
    sed -i -e "s/LOG_PATH = '.*'/LOG_PATH = '\/opt\/digiskr\/log'/g" /opt/digiskr/settings.py

WORKDIR /app/digiskr
VOLUME /opt/digiskr
ENV TZ=

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/app/digiskr/fetch.py"]