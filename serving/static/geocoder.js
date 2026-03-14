function initGeocoder(map) {
    var input = document.getElementById('geocoder-input');
    var resultsList = document.getElementById('geocoder-results');
    var clearBtn = document.getElementById('geocoder-clear');

    var CT_BBOX = '-73.73,40.95,-71.79,42.05';
    var CT_LAT = 41.6;
    var CT_LON = -72.7;

    var debounceTimer = null;
    var searchMarker = null;
    var activeIndex = -1;

    function clearMarker() {
        if (searchMarker) {
            searchMarker.remove();
            searchMarker = null;
        }
    }

    function hideResults() {
        resultsList.style.display = 'none';
        resultsList.innerHTML = '';
        activeIndex = -1;
    }

    function showClear(show) {
        clearBtn.style.display = show ? 'block' : 'none';
    }

    clearBtn.addEventListener('click', function () {
        input.value = '';
        hideResults();
        clearMarker();
        showClear(false);
        input.focus();
    });

    function formatLabel(props) {
        return [props.name, props.city, props.state, props.country]
            .filter(Boolean)
            .join(', ');
    }

    function selectResult(feature) {
        var coords = feature.geometry.coordinates;
        input.value = formatLabel(feature.properties);
        hideResults();
        showClear(true);

        clearMarker();
        searchMarker = new maplibregl.Marker({ color: '#4a90d9' })
            .setLngLat(coords)
            .addTo(map);

        map.flyTo({
            center: coords,
            zoom: 15,
            essential: true
        });
    }

    function renderResults(features) {
        resultsList.innerHTML = '';
        activeIndex = -1;

        if (features.length === 0) {
            resultsList.style.display = 'none';
            return;
        }

        features.forEach(function (feature) {
            var li = document.createElement('li');
            li.textContent = formatLabel(feature.properties);
            li.addEventListener('click', function () {
                selectResult(feature);
            });
            resultsList.appendChild(li);
        });

        resultsList.style.display = 'block';
    }

    function search(query) {
        var url = 'https://photon.komoot.io/api/?q=' +
            encodeURIComponent(query) +
            '&lat=' + CT_LAT +
            '&lon=' + CT_LON +
            '&bbox=' + CT_BBOX +
            '&limit=5' +
            '&lang=en';

        fetch(url)
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data && data.features) {
                    renderResults(data.features);
                }
            })
            .catch(function (err) {
                console.warn('Geocoder error:', err);
            });
    }

    input.addEventListener('input', function () {
        var val = input.value.trim();
        showClear(val.length > 0);

        if (val.length < 3) {
            hideResults();
            return;
        }

        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function () {
            search(val);
        }, 300);
    });

    input.addEventListener('keydown', function (e) {
        var items = resultsList.querySelectorAll('li');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            activeIndex = Math.min(activeIndex + 1, items.length - 1);
            items.forEach(function (li, i) {
                li.classList.toggle('active', i === activeIndex);
            });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            activeIndex = Math.max(activeIndex - 1, 0);
            items.forEach(function (li, i) {
                li.classList.toggle('active', i === activeIndex);
            });
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (activeIndex >= 0 && activeIndex < items.length) {
                items[activeIndex].click();
            } else if (items.length > 0) {
                items[0].click();
            }
        } else if (e.key === 'Escape') {
            hideResults();
            input.blur();
        }
    });

    document.addEventListener('click', function (e) {
        if (!document.getElementById('geocoder').contains(e.target)) {
            hideResults();
        }
    });
}
