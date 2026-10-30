import UIKit

final class PlaylistCell: UITableViewCell {
    @IBOutlet private weak var titleLabel: UILabel!
    @IBOutlet private weak var badgeView: UIImageView!

    static let equalizerIcons = ["eq_bass", "eq_treble", "eq_vocal"]

    func configure(with playlist: Playlist) {
        titleLabel.text = playlist.name
        badgeView.image = UIImage(named: playlist.trackCount > 50 ? "Badges/gold" : "missing-art")
    }

    static func register(in tableView: UITableView) {
        let cellClass: AnyClass? = NSClassFromString("PlaylistCell")
        tableView.register(cellClass, forCellReuseIdentifier: "PlaylistCell")
    }
}
