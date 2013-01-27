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
package org.nuxeo.drive.adapter;

import java.util.List;

import org.codehaus.jackson.annotate.JsonIgnore;
import org.nuxeo.drive.adapter.impl.DocumentBackedFolderItem;
import org.nuxeo.ecm.core.api.Blob;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.DocumentModel;

/**
 * Representation of a folder.
 * <p>
 * In the case of a {@link DocumentModel} backed implementation, the backing
 * document is Folderish. Typically a Folder or a Workspace.
 *
 * @author Antoine Taillefer
 * @see DocumentBackedFolderItem
 */
public interface FolderItem extends FileSystemItem {

    @JsonIgnore
    List<FileSystemItem> getChildren() throws ClientException;

    boolean getCanCreateChild();

    FileItem createFile(Blob blob) throws ClientException;

    FolderItem createFolder(String name) throws ClientException;

}
