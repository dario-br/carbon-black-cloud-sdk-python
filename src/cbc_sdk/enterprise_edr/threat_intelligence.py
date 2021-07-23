#!/usr/bin/env python3

# *******************************************************
# Copyright (c) VMware, Inc. 2020-2021. All Rights Reserved.
# SPDX-License-Identifier: MIT
# *******************************************************
# *
# * DISCLAIMER. THIS PROGRAM IS PROVIDED TO YOU "AS IS" WITHOUT
# * WARRANTIES OR CONDITIONS OF ANY KIND, WHETHER ORAL OR WRITTEN,
# * EXPRESS OR IMPLIED. THE AUTHOR SPECIFICALLY DISCLAIMS ANY IMPLIED
# * WARRANTIES OR CONDITIONS OF MERCHANTABILITY, SATISFACTORY QUALITY,
# * NON-INFRINGEMENT AND FITNESS FOR A PARTICULAR PURPOSE.

"""Model Classes for Enterprise Endpoint Detection and Response"""

from __future__ import absolute_import

import copy
import uuid

from cbc_sdk.errors import ApiError, InvalidObjectError, NonQueryableModel
from cbc_sdk.base import CreatableModelMixin, MutableBaseModel, UnrefreshableModel, SimpleQuery

import logging
import time
import validators

log = logging.getLogger(__name__)


"""Models"""


class FeedModel(UnrefreshableModel, CreatableModelMixin, MutableBaseModel):
    """A common base class for models used by the Feed and Watchlist APIs."""
    pass


class Watchlist(FeedModel):
    """Represents an Enterprise EDR watchlist."""
    # NOTE(ww): Not documented.
    urlobject = "/threathunter/watchlistmgr/v2/watchlist"
    urlobject_single = "/threathunter/watchlistmgr/v2/watchlist/{}"
    swagger_meta_file = "enterprise_edr/models/watchlist.yaml"

    @classmethod
    def _query_implementation(self, cb, **kwargs):
        return WatchlistQuery(self, cb)

    def __init__(self, cb, model_unique_id=None, initial_data=None):
        """
        Initialize the Watchlist object.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            model_unique_id (str): The unique ID of the watch list.
            initial_data (dict): The initial data for the object.
        """
        item = {}

        if initial_data:
            item = initial_data
        elif model_unique_id:
            item = cb.get_object(self.urlobject_single.format(model_unique_id))

        feed_id = item.get("id")

        super(Watchlist, self).__init__(cb, model_unique_id=feed_id, initial_data=item,
                                        force_init=False, full_doc=True)

    def save(self):
        """Saves this watchlist on the Enterprise EDR server.

        Returns:
            Watchlist (Watchlist): The saved Watchlist.

        Raises:
            InvalidObjectError: If Watchlist.validate() fails.
        """
        self.validate()

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists".format(
            self._cb.credentials.org_key
        )
        new_info = self._cb.post_object(url, self._info).json()
        self._info.update(new_info)
        return self

    def validate(self):
        """Validates this watchlist's state.

        Raises:
            InvalidObjectError: If the Watchlist's state is invalid.
        """
        super(Watchlist, self).validate()

    def update(self, **kwargs):
        """Updates this watchlist with the given arguments.

        Arguments:
            **kwargs (dict(str, str)): The fields to update.

        Raises:
            InvalidObjectError: If `id` is missing or Watchlist.validate() fails.
            ApiError: If `report_ids` is given and is empty.

        Example:

        >>> watchlist.update(name="New Name")


        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        # NOTE(ww): Special case, according to the docs.
        if "report_ids" in kwargs and not kwargs["report_ids"]:
            raise ApiError("can't update a watchlist to have an empty report list")

        for key, value in kwargs.items():
            if key in self._info:
                self._info[key] = value

        self.validate()

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}".format(
            self._cb.credentials.org_key,
            self.id
        )
        new_info = self._cb.put_object(url, self._info).json()
        self._info.update(new_info)

    @property
    def classifier_(self):
        """Returns the classifier key and value, if any, for this watchlist.

        Returns:
            tuple(str, str): Watchlist's classifier key and value.
            None: If there is no classifier key and value.
        """
        classifier_dict = self._info.get("classifier")

        if not classifier_dict:
            return None

        return (classifier_dict["key"], classifier_dict["value"])

    def delete(self):
        """Deletes this watchlist from the Enterprise EDR server.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.delete_object(url)

    def enable_alerts(self):
        """Enable alerts for this watchlist. Alerts are not retroactive.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}/alert".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.put_object(url, None)

    def disable_alerts(self):
        """Disable alerts for this watchlist.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}/alert".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.delete_object(url)

    def enable_tags(self):
        """Enable tagging for this watchlist.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}/tag".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.put_object(url, None)

    def disable_tags(self):
        """Disable tagging for this watchlist.

        Raises:
            InvalidObjectError: if `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing Watchlist ID")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/watchlists/{}/tag".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.delete_object(url)

    @property
    def feed(self):
        """Returns the Feed linked to this Watchlist, if there is one."""
        if not self.classifier:
            return None
        if self.classifier["key"] != "feed_id":
            log.warning("Unexpected classifier type: {}".format(self.classifier["key"]))
            return None

        return self._cb.select(Feed, self.classifier["value"])

    @property
    def reports(self):
        """Returns a list of Report objects associated with this watchlist.

        Returns:
            Reports ([Report]): List of Reports associated with the watchlist.

        Note:
            If this Watchlist is a classifier (i.e. feed-linked) Watchlist,
            `reports` will be empty. To get the reports associated with the linked
            Feed, use feed like:

            >>> for report in watchlist.feed.reports:
            ...     print(report.title)
        """
        if not self.report_ids:
            return []

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}"
        reports_ = []
        for rep_id in self.report_ids:
            path = url.format(self._cb.credentials.org_key, rep_id)
            resp = self._cb.get_object(path)
            reports_.append(Report(self._cb, initial_data=resp, from_watchlist=True))

        return reports_


class Feed(FeedModel):
    """Represents an Enterprise EDR feed's metadata."""
    urlobject = "/threathunter/feedmgr/v2/orgs/{}/feeds"
    urlobject_single = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}"
    primary_key = "id"
    swagger_meta_file = "enterprise_edr/models/feed.yaml"

    def __init__(self, cb, model_unique_id=None, initial_data=None):
        """
        Initialize the Feed object.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            model_unique_id (str): The unique ID of the feed.
            initial_data (dict): The initial data for the object.
        """
        item = {}
        reports = []

        if initial_data:
            # NOTE(ww): Some endpoints give us the full Feed, others give us just the FeedInfo.
            if "feedinfo" in initial_data:
                item = initial_data["feedinfo"]
                reports = initial_data.get("reports", [])
            else:
                item = initial_data
        elif model_unique_id:
            url = self.urlobject_single.format(
                cb.credentials.org_key, model_unique_id
            )
            resp = cb.get_object(url)
            item = resp.get("feedinfo", {})
            reports = resp.get("reports", [])

        feed_id = item.get("id")

        super(Feed, self).__init__(cb, model_unique_id=feed_id, initial_data=item,
                                   force_init=False, full_doc=True)

        self._reports = [Report(cb, initial_data=report, feed_id=feed_id) for report in reports]

    class FeedBuilder:
        """Helper class allowing Feeds to be assembled."""
        def __init__(self, cb, info):
            """
            Creates a new FeedBuilder object.

            Args:
                cb (CBCloudAPI): A reference to the CBCloudAPI object.
                info (dict): The initial information for the new feed.
            """
            self._cb = cb
            self._new_feedinfo = info
            self._reports = []

        def set_name(self, name):
            """
            Sets the name for the new feed.

            Args:
                name (str): New name for the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._new_feedinfo['name'] = name
            return self

        def set_provider_url(self, provider_url):
            """
            Sets the provider URL for the new feed.

            Args:
                provider_url (str): New provider URL for the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._new_feedinfo['provider_url'] = provider_url
            return self

        def set_summary(self, summary):
            """
            Sets the summary for the new feed.

            Args:
                summary (str): New summary for the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._new_feedinfo['summary'] = summary
            return self

        def set_category(self, category):
            """
            Sets the category for the new feed.

            Args:
                category (str): New category for the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._new_feedinfo['category'] = category
            return self

        def set_source_label(self, source_label):
            """
            Sets the source label for the new feed.

            Args:
                source_label (str): New source label for the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._new_feedinfo['source_label'] = source_label
            return self

        def add_reports(self, reports):
            """
            Adds new reports to the new feed.

            Args:
                reports (list[Report]): New reports to be added to the feed.

            Returns:
                FeedBuilder: This object.
            """
            self._reports += reports
            return self

        def build(self):
            """
            Builds the new Feed.

            Returns:
                Feed: The new Feed.
            """
            report_data = []
            for report in self._reports:
                report.validate()
                report_data.append(report._info)
            init_data = {'feedinfo': self._new_feedinfo, 'reports': report_data}
            return Feed(self._cb, None, init_data)

    @classmethod
    def create(cls, cb, name, provider_url, summary, category):
        """
        Begins creating a new feed by making a FeedBuilder to hold the new feed data.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            name (str): Name for the new feed.
            provider_url (str): Provider URL for the new feed.
            summary (str): Summary for the new feed.
            category (str): Category for the new feed.

        Returns:
            FeedBuilder: The new FeedBuilder object to be used to create the feed.
        """
        return Feed.FeedBuilder(cb, {'name': name, 'provider_url': provider_url, 'summary': summary,
                                     'category': category})

    @classmethod
    def _query_implementation(self, cb, **kwargs):
        """
        Returns the appropriate query object for Feeds.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            **kwargs (dict): Not used, retained for compatibility.

        Returns:
            FeedQuery: The query object for Feeds.
        """
        return FeedQuery(self, cb)

    def save(self, public=False):
        """
        Saves this feed on the Enterprise EDR server.

        Arguments:
            public (bool): Whether to make the feed publicly available.

        Returns:
            Feed (Feed): The saved Feed.
        """
        self.validate()

        body = {
            'feedinfo': self._info,
            'reports': [report._info for report in self._reports],
        }

        url = "/threathunter/feedmgr/v2/orgs/{}/feeds".format(
            self._cb.credentials.org_key
        )
        if public:
            url = url + "/public"

        new_info = self._cb.post_object(url, body).json()
        self._info.update(new_info['feedinfo'])
        self._reports = [Report(self._cb, initial_data=report, feed_id=new_info['feedinfo']['id'])
                         for report in new_info['reports']]
        return self

    def validate(self):
        """
        Validates this feed's state.

        Raises:
            InvalidObjectError: If the Feed's state is invalid.
        """
        id_substitute = False
        if not self._info.get('id', None):
            self._info['id'] = '*'
            id_substitute = True
        owner_substitute = False
        if not self._info.get('owner', None):
            self._info['owner'] = '*'
            owner_substitute = True
        access_substitute = False
        if not self._info.get('access', None):
            self._info['access'] = '*'
            access_substitute = True
        super(Feed, self).validate()
        if id_substitute:
            del self._info['id']
        if owner_substitute:
            del self._info['owner']
        if access_substitute:
            del self._info['access']

        if self.access and self.access not in ["public", "private"]:
            raise InvalidObjectError("access should be public or private")

        if not validators.url(self.provider_url):
            raise InvalidObjectError("provider_url should be a valid URL")

        for report in self._reports:
            report.validate()

    def delete(self):
        """
        Deletes this feed from the Enterprise EDR server.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing feed ID")

        url = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.delete_object(url)

    def update(self, **kwargs):
        """
        Update this feed's metadata with the given arguments.

        Arguments:
            **kwargs (dict(str, str)): The fields to update.

        Raises:
            InvalidObjectError: If `id` is missing or Feed.validate() fails.
            ApiError: If an invalid field is specified.

        Example:

        >>> feed.update(access="private")
        """
        if not self.id:
            raise InvalidObjectError("missing feed ID")

        for key, value in kwargs.items():
            if key in self._info:
                self._info[key] = value

        self.validate()

        url = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}/feedinfo".format(
            self._cb.credentials.org_key,
            self.id,
        )
        new_info = self._cb.put_object(url, self._info).json()
        self._info.update(new_info)

        return self

    @property
    def reports(self):
        """
        Returns a list of Reports associated with this feed.

        Returns:
            Reports ([Report]): List of Reports in this Feed.
        """
        self._reports = list(self._cb.select(Report).where(feed_id=self.id))
        return self._reports

    def _overwrite_reports(self, reports):
        """
        Overwrites the Reports in this Feed with the given Reports.

        Arguments:
            reports ([Report]): List of Reports to replace existing Reports with.
        """
        rep_dicts = []
        for report in reports:
            report.validate()
            rep_dicts.append(report._info)
        body = {"reports": rep_dicts}

        url = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}/reports".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.post_object(url, body)
        self._reports = reports

    def replace_reports(self, reports):
        """
        Replace this Feed's Reports with the given Reports.

        Arguments:
            reports ([Report]): List of Reports to replace existing Reports with.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing feed ID")
        self._overwrite_reports(reports)

    def append_reports(self, reports):
        """
        Append the given Reports to this Feed's current Reports.

        Arguments:
            reports ([Report]): List of Reports to append to Feed.

        Raises:
            InvalidObjectError: If `id` is missing.
        """
        if not self.id:
            raise InvalidObjectError("missing feed ID")
        self._overwrite_reports(self._reports + reports)


class Report(FeedModel):
    """Represents reports retrieved from an Enterprise EDR feed."""
    urlobject = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}/reports"
    primary_key = "id"
    swagger_meta_file = "enterprise_edr/models/report.yaml"

    @classmethod
    def _query_implementation(self, cb, **kwargs):
        """
        Returns the appropriate query object for Reports.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            **kwargs (dict): Not used, retained for compatibility.

        Returns:
            ReportQuery: The query object for Reports.
        """
        return ReportQuery(self, cb)

    def __init__(self, cb, model_unique_id=None, initial_data=None,
                 feed_id=None, from_watchlist=False):
        """
        Initialize the ReportSeverity object.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            model_unique_id (Any): Unused.
            initial_data (dict): The initial data for the object.
            feed_id (str): The ID of the feed this report is for.
            from_watchlist (str): The ID of the watchlist this report is for.
        """
        super(Report, self).__init__(cb, model_unique_id=initial_data.get("id", None),
                                     initial_data=initial_data,
                                     force_init=False, full_doc=True)

        # NOTE(ww): Warn instead of failing since we allow Watchlist reports
        # to be created via create(), but we don't actually know that the user
        # intends to use them with a watchlist until they call save().
        if not feed_id and not from_watchlist:
            log.warning("Report created without feed ID or not from watchlist")

        self._feed_id = feed_id
        self._from_watchlist = from_watchlist

        if self.iocs:
            self._iocs = IOC(cb, initial_data=self.iocs, report_id=self.id)
        if self.iocs_v2:
            self._iocs_v2 = [IOC_V2(cb, initial_data=ioc, report_id=self.id) for ioc in self.iocs_v2]
        self._iocs_v2_need_sync = False

    class ReportBuilder:
        """Helper class allowing Reports to be assembled."""
        def __init__(self, cb, report_body):
            """
            Initialize a new ReportBuilder.

            Args:
                cb (CBCloudAPI): A reference to the CBCloudAPI object.
                report_body (dict): Partial report body which should be filled in with all "required" fields.
            """
            self._cb = cb
            self._report_body = report_body
            self._report_body['tags'] = []
            self._iocs = []

        def set_title(self, title):
            """
            Set the title for the new report.

            Args:
                title (str): New title for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['title'] = title
            return self

        def set_description(self, description):
            """
            Set the description for the new report.

            Args:
                description (str): New description for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['description'] = description
            return self

        def set_timestamp(self, timestamp):
            """
            Set the timestamp for the new report.

            Args:
                timestamp (int): New timestamp for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['timestamp'] = timestamp
            return self

        def set_severity(self, severity):
            """
            Set the severity for the new report.

            Args:
                severity (int): New severity for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['severity'] = severity
            return self

        def set_link(self, link):
            """
            Set the link for the new report.

            Args:
                link (str): New link for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['link'] = link
            return self

        def add_tag(self, tag):
            """
            Adds a tag value to the new report.

            Args:
                tag (str): The new tag for the object.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['tags'].append(tag)
            return self

        def add_ioc(self, ioc):
            """
            Adds an IOC to the new report.

            Args:
                ioc (IOC_V2): The IOC to be added to the report.

            Returns:
                ReportBuilder: This object.
            """
            self._iocs.append(ioc)
            return self

        def set_visibility(self, visibility):
            """
            Set the visibility for the new report.

            Args:
                visibility (str): New visibility for the report.

            Returns:
                ReportBuilder: This object.
            """
            self._report_body['visibility'] = visibility
            return self

        def build(self):
            """
            Builds the actual Report from the internal data of the ReportBuilder.

            Returns:
                Report: The new Report.
            """
            report = Report(self._cb, None, self._report_body)
            report._iocs_v2 = self._iocs
            report._iocs_v2_need_sync = True
            return report

    @classmethod
    def create(cls, cb, title, description, severity, timestamp=None):
        """
        Begin creating a new Report by returning a ReportBuilder.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            title (str): Title for the new report.
            description (str): Description for the new report.
            severity (int): Severity value for the new report.
            timestamp (int): UNIX-epoch timestamp for the new report. If omitted, current time will be used.

        Returns:
            ReportBuilder: Reference to the ReportBuilder object.
        """
        if not timestamp:
            timestamp = int(time.time())
        return Report.ReportBuilder(cb, {'title': title, 'description': description, 'severity': severity,
                                         'timestamp': timestamp})

    def save_watchlist(self):
        """
        Saves this report *as a watchlist report*.

        Note:
            This method **cannot** be used to save a feed report. To save feed reports, create them with `cb.create`
            and use `Feed.replace`.

        Raises:
            InvalidObjectError: If Report.validate() fails.
        """
        self.validate()

        # NOTE(ww): Once saved, this object corresponds to a watchlist report.
        # As such, we need to tell the model to route calls like update()
        # and delete() to the correct (watchlist) endpoints.
        self._from_watchlist = True

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports".format(
            self._cb.credentials.org_key
        )
        new_info = self._cb.post_object(url, self._info).json()
        self._info.update(new_info)
        return self

    def validate(self):
        """
        Validates this report's state.

        Raises:
            InvalidObjectError: If the report's state is invalid.
        """
        id_substitute = False
        if not self._info.get('id', None):
            self._info['id'] = '*'
            id_substitute = True
        super(Report, self).validate()
        if id_substitute:
            del self._info['id']

        if self.link and not validators.url(self.link):
            raise InvalidObjectError("link should be a valid URL")

        if self.iocs_v2:
            [ioc.validate() for ioc in self._iocs_v2]
        if self._iocs_v2_need_sync:
            self._info['iocs_v2'] = [ioc._info for ioc in self._iocs_v2]
            self._iocs_v2_need_sync = False

    def update(self, **kwargs):
        """Update this Report with the given arguments.

        Arguments:
            **kwargs (dict(str, str)): The Report fields to update.

        Returns:
            Report (Report): The updated Report.

        Raises:
            InvalidObjectError: If `id` is missing, or `feed_id` is missing
                and this report is a Feed Report, or Report.validate() fails.

        Note:
            The report's timestamp is always updated, regardless of whether passed explicitly.

        >>> report.update(title="My new report title")
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")

        if self._from_watchlist:
            url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}".format(
                self._cb.credentials.org_key,
                self.id
            )
        else:
            if not self._feed_id:
                raise InvalidObjectError("missing Feed ID")
            url = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}/reports/{}".format(
                self._cb.credentials.org_key,
                self._feed_id,
                self.id
            )

        iocs_v2_poked = False
        for key, value in kwargs.items():
            if key in self._info:
                self._info[key] = value
            if key == 'iocs_v2':
                iocs_v2_poked = True

        if self.iocs:
            self._iocs = IOC(self._cb, initial_data=self.iocs, report_id=self.id)
        if self.iocs_v2 and iocs_v2_poked:
            self._iocs_v2 = [IOC_V2(self._cb, initial_data=ioc, report_id=self.id) for ioc in self.iocs_v2]
            self._iocs_v2_need_sync = False

        # NOTE(ww): Updating reports on the watchlist API appears to require
        # updated timestamps.
        self.timestamp = int(time.time())
        self.validate()

        new_info = self._cb.put_object(url, self._info).json()
        self._info.update(new_info)
        return self

    def delete(self):
        """Deletes this report from the Enterprise EDR server.

        Raises:
            InvalidObjectError: If `id` is missing, or `feed_id` is missing
                and this report is a Feed Report.

        Example:

        >>> report.delete()
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")

        if self._from_watchlist:
            url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}".format(
                self._cb.credentials.org_key,
                self.id
            )
        else:
            if not self._feed_id:
                raise InvalidObjectError("missing Feed ID")
            url = "/threathunter/feedmgr/v2/orgs/{}/feeds/{}/reports/{}".format(
                self._cb.credentials.org_key,
                self._feed_id,
                self.id
            )

        self._cb.delete_object(url)

    @property
    def ignored(self):
        """Returns the ignore status for this report.

        Only watchlist reports have an ignore status.

        Returns:
            (bool): True if this Report is ignored, False otherwise.

        Raises:
            InvalidObjectError: If `id` is missing or this Report is not from a Watchlist.

        Example:

        >>> if report.ignored:
        ...     report.unignore()
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")
        if not self._from_watchlist:
            raise InvalidObjectError("ignore status only applies to watchlist reports")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/ignore".format(
            self._cb.credentials.org_key,
            self.id
        )
        resp = self._cb.get_object(url)
        return resp["ignored"]

    def ignore(self):
        """Sets the ignore status on this report.

        Only watchlist reports have an ignore status.

        Raises:
            InvalidObjectError: If `id` is missing or this Report is not from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")

        if not self._from_watchlist:
            raise InvalidObjectError("ignoring only applies to watchlist reports")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/ignore".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.put_object(url, None)

    def unignore(self):
        """Removes the ignore status on this report.

        Only watchlist reports have an ignore status.

        Raises:
            InvalidObjectError: If `id` is missing or this Report is not from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")

        if not self._from_watchlist:
            raise InvalidObjectError("ignoring only applies to watchlist reports")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/ignore".format(
            self._cb.credentials.org_key,
            self.id
        )
        self._cb.delete_object(url)

    @property
    def custom_severity(self):
        """Returns the custom severity for this report.

        Returns:
            ReportSeverity (ReportSeverity): The custom severity for this Report,
                if it exists.

        Raises:
            InvalidObjectError: If `id` ismissing or this Report is from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing report ID")
        if self._from_watchlist:
            raise InvalidObjectError("watchlist reports don't have custom severities")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/severity".format(
            self._cb.credentials.org_key,
            self.id
        )
        resp = self._cb.get_object(url)
        return ReportSeverity(self._cb, initial_data=resp)

    @custom_severity.setter
    def custom_severity(self, sev_level):
        """Sets or removed the custom severity for this report.

        Arguments:
            sev_level (int): The new severity, or None to remove the custom severity.

        Returns:
            ReportSeverity (ReportSeverity): The new custom severity.
            None: If the custom severity was removed.

        Raises:
            InvalidObjectError: If `id` is missing or this Report is from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing report ID")
        if self._from_watchlist:
            raise InvalidObjectError("watchlist reports don't have custom severities")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/severity".format(
            self._cb.credentials.org_key,
            self.id
        )

        if sev_level is None:
            self._cb.delete_object(url)
            return

        args = {
            "report_id": self.id,
            "severity": sev_level,
        }

        resp = self._cb.put_object(url, args).json()
        return ReportSeverity(self._cb, initial_data=resp)

    @property
    def iocs_(self):
        """Returns a list of IOC_V2's associated with this report.

        Returns:
            IOC_V2 ([IOC_V2]): List of IOC_V2's for associated with the Report.

        Example:

        >>> for ioc in report.iocs_:
        ...     print(ioc.values)
        """
        if not self.iocs_v2:
            return []

        # NOTE(ww): This name is underscored because something in the model
        # hierarchy is messing up method resolution -- self.iocs and self.iocs_v2
        # are resolving to the attributes rather than the attribute-ified
        # methods.
        return self._iocs_v2

    def append_iocs(self, iocs):
        """
        Append a list of IOCs to this Report.

        Args:
            iocs (list[IOC_V2]): List of IOCs to be added.
        """
        if self.iocs_v2:
            self._iocs_v2 += iocs
        else:
            self._iocs_v2 = iocs
        self._iocs_v2_need_sync = True

    def remove_iocs_by_id(self, ids_list):
        """
        Remove IOCs from this report by specifying their IDs.

        Args:
            ids_list (list[str]): List of IDs of the IOCs to be removed.
        """
        if self.iocs_v2:
            id_set = set(ids_list)
            old_len = len(self._iocs_v2)
            self._iocs_v2 = [ioc for ioc in self._iocs_v2 if ioc._info['id'] not in id_set]
            self._iocs_v2_need_sync = (old_len > len(self._iocs_v2))

    def remove_iocs(self, iocs):
        """
        Remove a list of IOCs from this Report.

        Args:
            iocs (list[IOC_V2]): List of IOCs to be removed.
        """
        if self.iocs_v2:
            self.remove_iocs_by_id([ioc._info['id'] for ioc in iocs])


class ReportSeverity(FeedModel):
    """Represents severity information for a Watchlist Report."""
    primary_key = "report_id"
    swagger_meta_file = "enterprise_edr/models/report_severity.yaml"

    def __init__(self, cb, initial_data=None):
        """
        Initialize the ReportSeverity object.

        Args:
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
            initial_data (dict): The initial data for the object.
        """
        if not initial_data:
            raise ApiError("ReportSeverity can only be initialized from initial_data")

        super(ReportSeverity, self).__init__(cb, model_unique_id=initial_data.get(self.primary_key),
                                             initial_data=initial_data, force_init=False,
                                             full_doc=True)

    def _query_implementation(self, cb, **kwargs):
        """
        Queries are not supported for report severity, so this raises an exception.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            **kwargs (dict): Additional arguments.

        Raises:
            NonQueryableModel: Always.
        """
        raise NonQueryableModel("ReportSeverity does not support querying")


class IOC(FeedModel):
    """Represents a collection of categorized IOCs.  These objects are officially deprecated and replaced by IOC_V2."""
    swagger_meta_file = "enterprise_edr/models/iocs.yaml"

    def __init__(self, cb, model_unique_id=None, initial_data=None, report_id=None):
        """
        Creates a new IOC instance.

        Arguments:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            model_unique_id (str): Unique ID of this IOC.
            initial_data (dict): Initial data used to populate the IOC.
            report_id (str): ID of the report this IOC belongs to (if this is a watchlist IOC).

        Raises:
            ApiError: If `initial_data` is None.
        """
        if not initial_data:
            raise ApiError("IOC can only be initialized from initial_data")

        super(IOC, self).__init__(cb, model_unique_id=model_unique_id, initial_data=initial_data,
                                  force_init=False, full_doc=True)

        self._report_id = report_id

    def _query_implementation(self, cb, **kwargs):
        """
        Queries are not supported for IOCs, so this raises an exception.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            **kwargs (dict): Additional arguments.

        Raises:
            NonQueryableModel: Always.
        """
        raise NonQueryableModel("IOC does not support querying")

    def validate(self):
        """
        Validates this IOC structure's state.

        Raises:
            InvalidObjectError: If the IOC structure's state is invalid.
        """
        super(IOC, self).validate()

        for md5 in self.md5:
            if not validators(md5):
                raise InvalidObjectError("invalid MD5 checksum: {}".format(md5))
        for ipv4 in self.ipv4:
            if not validators(ipv4):
                raise InvalidObjectError("invalid IPv4 address: {}".format(ipv4))
        for ipv6 in self.ipv6:
            if not validators(ipv6):
                raise InvalidObjectError("invalid IPv6 address: {}".format(ipv6))
        for dns in self.dns:
            if not validators(dns):
                raise InvalidObjectError("invalid domain: {}".format(dns))
        for query in self.query:
            if not self._cb.validate(query["search_query"]):
                raise InvalidObjectError("invalid search query: {}".format(query["search_query"]))


class IOC_V2(FeedModel):
    """Represents a collection of IOCs of a particular type, plus matching criteria and metadata."""
    primary_key = "id"
    swagger_meta_file = "enterprise_edr/models/ioc_v2.yaml"

    def __init__(self, cb, model_unique_id=None, initial_data=None, report_id=None):
        """
        Creates a new IOC_V2 instance.

        Arguments:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            model_unique_id (Any): Unused.
            initial_data (dict): Initial data used to populate the IOC.
            report_id (str): ID of the report this IOC belongs to (if this is a watchlist IOC).

        Raises:
            ApiError: If `initial_data` is None.
        """
        if not initial_data:
            raise ApiError("IOC_V2 can only be initialized from initial_data")

        super(IOC_V2, self).__init__(cb, model_unique_id=initial_data.get(self.primary_key),
                                     initial_data=initial_data, force_init=False,
                                     full_doc=True)

        self._report_id = report_id

    def _query_implementation(self, cb, **kwargs):
        """
        Queries are not supported for IOCs, so this raises an exception.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            **kwargs (dict): Additional arguments.

        Raises:
            NonQueryableModel: Always.
        """
        raise NonQueryableModel("IOC_V2 does not support querying")

    @classmethod
    def create_query(cls, cb, iocid, query):
        """
        Creates a new "query" IOC.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            iocid (str): ID for the new IOC.  If this is None, a UUID will be generated for the IOC.
            query (str): Query to be incorporated in this IOC.

        Returns:
            IOC_V2: New IOC data structure.

        Raises:
            ApiError: If the query string is not present.
        """
        if not query:
            raise ApiError("IOC must have a query string")
        if not iocid:
            iocid = str(uuid.uuid4())
        return IOC_V2(cb, iocid, {'id': iocid, 'match_type': 'query', 'values': [query]})

    @classmethod
    def create_equality(cls, cb, iocid, field, *values):
        """
        Creates a new "equality" IOC.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            iocid (str): ID for the new IOC.  If this is None, a UUID will be generated for the IOC.
            field (str): Name of the field to be matched by this IOC.
            *values (list(str)): String values to match against the value of the specified field.

        Returns:
            IOC_V2: New IOC data structure.

        Raises:
            ApiError: If there is not at least one value to match against.
        """
        if not field:
            raise ApiError('IOC must have a field name')
        if len(values) == 0:
            raise ApiError('IOC must have at least one value')
        if not iocid:
            iocid = str(uuid.uuid4())
        return IOC_V2(cb, iocid, {'id': iocid, 'match_type': 'equality', 'field': field, 'values': list(values)})

    @classmethod
    def create_regex(cls, cb, iocid, field, *values):
        """
        Creates a new "regex" IOC.

        Args:
            cb (BaseAPI): Reference to API object used to communicate with the server.
            iocid (str): ID for the new IOC.  If this is None, a UUID will be generated for the IOC.
            field (str): Name of the field to be matched by this IOC.
            *values (list(str)): Regular expression values to match against the value of the specified field.

        Returns:
            IOC_V2: New IOC data structure.

        Raises:
            ApiError: If there is not at least one regular expression to match against.
        """
        if not field:
            raise ApiError('IOC must have a field name')
        if len(values) == 0:
            raise ApiError('IOC must have at least one value')
        if not iocid:
            iocid = str(uuid.uuid4())
        return IOC_V2(cb, iocid, {'id': iocid, 'match_type': 'regex', 'field': field, 'values': list(values)})

    def validate(self):
        """
        Validates this IOC_V2's state.

        Raises:
            InvalidObjectError: If the IOC_V2's state is invalid.
        """
        super(IOC_V2, self).validate()

        if self.link and not validators.url(self.link):
            raise InvalidObjectError("link should be a valid URL")

    @property
    def ignored(self):
        """
        Returns whether or not this IOC is ignored.

        Only watchlist IOCs have an ignore status.

        Returns:
            bool: True if the IOC is ignored, False otherwise.

        Raises:
            InvalidObjectError: If this IOC is missing an `id` or is not a Watchlist IOC.

        Example:

        >>> if ioc.ignored:
        ...     ioc.unignore()
        """
        if not self.id:
            raise InvalidObjectError("missing IOC ID")
        if not self._report_id:
            raise InvalidObjectError("ignore status only applies to watchlist IOCs")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/iocs/{}/ignore".format(
            self._cb.credentials.org_key,
            self._report_id,
            self.id
        )
        resp = self._cb.get_object(url)
        return resp["ignored"]

    def ignore(self):
        """
        Sets the ignore status on this IOC.

        Only watchlist IOCs have an ignore status.

        Raises:
            InvalidObjectError: If `id` is missing or this IOC is not from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")
        if not self._report_id:
            raise InvalidObjectError("ignoring only applies to watchlist IOCs")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/iocs/{}/ignore".format(
            self._cb.credentials.org_key,
            self._report_id,
            self.id
        )
        self._cb.put_object(url, None)

    def unignore(self):
        """
        Removes the ignore status on this IOC.

        Only watchlist IOCs have an ignore status.

        Raises:
            InvalidObjectError: If `id` is missing or this IOC is not from a Watchlist.
        """
        if not self.id:
            raise InvalidObjectError("missing Report ID")
        if not self._report_id:
            raise InvalidObjectError("ignoring only applies to watchlist IOCs")

        url = "/threathunter/watchlistmgr/v3/orgs/{}/reports/{}/iocs/{}/ignore".format(
            self._cb.credentials.org_key,
            self._report_id,
            self.id
        )
        self._cb.delete_object(url)


"""Queries"""


class FeedQuery(SimpleQuery):
    """Represents the logic for a Feed query.

    >>> cb.select(Feed)
    >>> cb.select(Feed, id)
    >>> cb.select(Feed).where(include_public=True)
    """
    def __init__(self, doc_class, cb):
        """
        Initialize the FeedQuery object.

        Args:
            doc_class (class): The class of the model this query returns.
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
        """
        super(FeedQuery, self).__init__(doc_class, cb)
        self._args = {}

    def where(self, **kwargs):
        """Add kwargs to self._args dictionary."""
        self._args = dict(self._args, **kwargs)
        return self

    @property
    def results(self):
        """Return a list of Feed objects matching self._args parameters."""
        log.debug("Fetching all feeds")
        url = self._doc_class.urlobject.format(self._cb.credentials.org_key)
        resp = self._cb.get_object(url, query_parameters=self._args)
        results = resp.get("results", [])
        return [self._doc_class(self._cb, initial_data=item) for item in results]


class ReportQuery(SimpleQuery):
    """Represents the logic for a Report query.

    Note:
        Only feed reports can be queried. Watchlist reports should be interacted
            with via Watchlist.reports().

    Example:
    >>> cb.select(Report).where(feed_id=id)
    """
    def __init__(self, doc_class, cb):
        """
        Initialize the ReportQuery object.

        Args:
            doc_class (class): The class of the model this query returns.
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
        """
        super(ReportQuery, self).__init__(doc_class, cb)
        self._args = {}

    def where(self, **kwargs):
        """Add kwargs to self._args dictionary."""
        self._args = dict(self._args, **kwargs)
        return self

    @property
    def results(self):
        """Return a list of Report objects matching self._args['feed_id']."""
        if "feed_id" not in self._args:
            raise ApiError("required parameter feed_id missing")

        feed_id = self._args["feed_id"]

        log.debug("Fetching all reports")
        url = self._doc_class.urlobject.format(
            self._cb.credentials.org_key,
            feed_id,
        )
        resp = self._cb.get_object(url)
        results = resp.get("results", [])
        return [self._doc_class(self._cb, initial_data=item, feed_id=feed_id) for item in results]


class WatchlistQuery(SimpleQuery):
    """Represents the logic for a Watchlist query.

    >>> cb.select(Watchlist)
    """
    def __init__(self, doc_class, cb):
        """
        Initialize the WatchlistQuery object.

        Args:
            doc_class (class): The class of the model this query returns.
            cb (CBCloudAPI): A reference to the CBCloudAPI object.
        """
        super(WatchlistQuery, self).__init__(doc_class, cb)

    @property
    def results(self):
        """Return a list of all Watchlist objects."""
        log.debug("Fetching all watchlists")

        resp = self._cb.get_object(self._doc_class.urlobject)
        results = resp.get("results", [])
        return [self._doc_class(self._cb, initial_data=item) for item in results]
