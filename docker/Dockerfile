FROM lazywalker/digiskr-base:latest

COPY settings.py.template /opt/digiskr/settings.py
COPY docker/entrypoint.sh /entrypoint.sh
COPY . /app/digiskr

# set TMP_PATH and LOG_PATH
RUN sed -i -e "s/TMP_PATH = '.*'/TMP_PATH = '\/tmp\/digiskr'/g" /opt/digiskr/settings.py && \
    sed -i -e "s/LOG_PATH = '.*'/LOG_PATH = '\/opt\/digiskr\/log'/g" /opt/digiskr/settings.py

WORKDIR /app/digiskr
VOLUME /opt/digiskr
ENV TZ set_me

ENTRYPOINT ["/entrypoint.sh"]
CMD ["/app/digiskr/fetch.py"]