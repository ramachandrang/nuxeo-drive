/*
 * (C) Copyright 2012 Nuxeo SA (http://nuxeo.com/) and contributors.
 *
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the GNU Lesser General Public License
 * (LGPL) version 2.1 which accompanies this distribution, and is available at
 * http://www.gnu.org/licenses/lgpl.html
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * Contributors:
 *     Antoine Taillefer <ataillefer@nuxeo.com>
 */
package org.nuxeo.drive.operations;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.nuxeo.drive.operations.test.NuxeoDriveSetVersioningOptions;
import org.nuxeo.drive.service.FileSystemItemAdapterService;
import org.nuxeo.drive.service.VersioningFileSystemItemFactory;
import org.nuxeo.drive.service.impl.FileSystemItemAdapterServiceImpl;
import org.nuxeo.ecm.automation.client.Session;
import org.nuxeo.ecm.automation.client.jaxrs.impl.HttpAutomationClient;
import org.nuxeo.ecm.automation.test.RestFeature;
import org.nuxeo.ecm.core.api.VersioningOption;
import org.nuxeo.runtime.test.runner.Deploy;
import org.nuxeo.runtime.test.runner.Features;
import org.nuxeo.runtime.test.runner.FeaturesRunner;
import org.nuxeo.runtime.test.runner.Jetty;

import com.google.inject.Inject;

/**
 * Tests the {@link NuxeoDriveSetVersioningOptions} operation.
 *
 * @author Antoine Taillefer
 */
@RunWith(FeaturesRunner.class)
@Features(RestFeature.class)
@Deploy({ "org.nuxeo.drive.core", "org.nuxeo.drive.operations" })
@Jetty(port = 18080)
public class TestSetVersioningOptions {

    @Inject
    protected FileSystemItemAdapterService fileSystemItemAdapterService;

    @Inject
    protected HttpAutomationClient automationClient;

    protected VersioningFileSystemItemFactory defaultFileSystemItemFactory;

    protected Session clientSession;

    @Before
    public void init() throws Exception {

        defaultFileSystemItemFactory = (VersioningFileSystemItemFactory) ((FileSystemItemAdapterServiceImpl) fileSystemItemAdapterService).getFileSystemItemFactory("defaultFileSystemItemFactory");
        assertNotNull(defaultFileSystemItemFactory);

        // Get an Automation client session as Administrator
        clientSession = automationClient.getSession("Administrator",
                "Administrator");
    }

    @Test
    public void testSetVersioningOptions() throws Exception {

        // Default values
        assertEquals(3600.0, defaultFileSystemItemFactory.getVersioningDelay(),
                .01);
        assertEquals(VersioningOption.MINOR,
                defaultFileSystemItemFactory.getVersioningOption());

        // Set delay to 2 seconds
        clientSession.newRequest(NuxeoDriveSetVersioningOptions.ID).set(
                "delay", "2").execute();
        assertEquals(2.0, defaultFileSystemItemFactory.getVersioningDelay(),
                .01);
        assertEquals(VersioningOption.MINOR,
                defaultFileSystemItemFactory.getVersioningOption());

        // Set option to MAJOR
        clientSession.newRequest(NuxeoDriveSetVersioningOptions.ID).set(
                "option", "MAJOR").execute();
        assertEquals(2.0, defaultFileSystemItemFactory.getVersioningDelay(),
                .01);
        assertEquals(VersioningOption.MAJOR,
                defaultFileSystemItemFactory.getVersioningOption());

    }

}
