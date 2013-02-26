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

import org.codehaus.plexus.util.StringUtils;
import org.nuxeo.drive.adapter.FileItem;
import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.service.FileSystemItemManager;
import org.nuxeo.ecm.automation.OperationContext;
import org.nuxeo.ecm.automation.core.Constants;
import org.nuxeo.ecm.automation.core.annotations.Context;
import org.nuxeo.ecm.automation.core.annotations.Operation;
import org.nuxeo.ecm.automation.core.annotations.OperationMethod;
import org.nuxeo.ecm.automation.core.annotations.Param;
import org.nuxeo.ecm.core.api.Blob;
import org.nuxeo.runtime.api.Framework;

/**
 * Creates a file with the given blob in the {@link FileSystemItem} with the
 * given id for the currently authenticated user.
 *
 * @author Antoine Taillefer
 */
@Operation(id = NuxeoDriveCreateFile.ID, category = Constants.CAT_SERVICES, label = "Nuxeo Drive: Create file")
public class NuxeoDriveCreateFile {

    public static final String ID = "NuxeoDrive.CreateFile";

    @Context
    protected OperationContext ctx;

    @Param(name = "parentId")
    protected String parentId;

    @Param(name = "name")
    protected String name;

    @OperationMethod
    public Blob run(Blob blob) throws Exception {

        FileSystemItemManager fileSystemItemManager = Framework.getLocalService(FileSystemItemManager.class);
        // The filename transfered by the multipart encoding is not preserved
        // correctly if there is non ascii characters in it.
        if (StringUtils.isNotBlank(name)) {
            blob.setFilename(name);
        }
        NuxeoDriveOperationHelper.normalizeMimeTypeAndEncoding(blob);
        FileItem fileItem = fileSystemItemManager.createFile(parentId, blob,
                ctx.getPrincipal());

        // Commit transaction explicitly to ensure client-side consistency
        // TODO: remove when https://jira.nuxeo.com/browse/NXP-10964 is fixed
        NuxeoDriveOperationHelper.commitAndReopenTransaction();
        return NuxeoDriveOperationHelper.asJSONBlob(fileItem);
    }

}
