FROM alpine:3.5
MAINTAINER Nobuo OKAZAKI
RUN apk add --no-cache python2 py2-bottle bash \
 && adduser -u 1000 -D bottle bottle \
 && rm -rf /tmp/* /media /mnt /run /srv
ADD ./ /opt/regiui/
ADD .git/HEAD /tmp/.git/
ADD .git/refs /tmp/.git/refs
RUN GITREF=$(cat /tmp/.git/HEAD | cut -d" " -f2) \
 && GITSHA1=$(cat /tmp/.git/$GITREF) \
 && GITBR=$(echo refs/heads/master | cut -d/ -f3) \
 && echo "{\"git\":{\"sha1\":\"$GITSHA1\",\"branch\":\"$GITBR\"}}" > /opt/regiui/public/version.json \
 && rm -rf /tmp/* /media /mnt /run /srv
ENV PYTHONPATH /opt/regiui/lib:$PYTHONPATH
USER bottle
ENTRYPOINT ["bottle.py", \
  "-b", "0.0.0.0:8000", \
  "regiui" \
]
EXPOSE 8000
